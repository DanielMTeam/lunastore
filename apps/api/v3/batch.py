import logging
from copy import copy
from urllib.parse import urlsplit

from django.http import Http404, QueryDict
from django.urls import NoReverseMatch, resolve, reverse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .contract import V3ContractMixin, problem


logger = logging.getLogger(__name__)


# Keys are public operationIds. Values are names of the same GET routes used by direct clients.
BATCH_OPERATIONS = {
    "v3_apps_list": ("v3-app-list", False),
    "v3_apps_retrieve": ("v3-app-detail", True),
    "v3_apps_distributions_list": ("v3-app-distributions", True),
    "v3_categories_list": ("v3-category-list", False),
    "v3_categories_retrieve": ("v3-category-detail", True),
    "v3_categories_apps_list": ("v3-category-apps", True),
    "v3_collections_list": ("v3-collection-list", False),
    "v3_collections_retrieve": ("v3-collection-detail", True),
    "v3_collections_apps_list": ("v3-collection-apps", True),
    "v3_distributions_list": ("v3-distribution-list", False),
    "v3_distributions_retrieve": ("v3-distribution-detail", True),
    "v3_platforms_list": ("v3-platform-list", False),
    "v3_platforms_retrieve": ("v3-platform-detail", True),
    "v3_users_list": ("v3-user-list", False),
    "v3_users_retrieve": ("v3-user-detail", True),
    "v3_search_suggestions_retrieve": ("v3-suggestions", False),
}


class BatchAuthentication(BaseAuthentication):
    def authenticate(self, request):
        return request._request.batch_identity


class BatchCallSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=64)
    operation = serializers.CharField(max_length=100)
    params = serializers.DictField(required=False, default=dict)

    def validate_params(self, value):
        if len(value) > 16:
            raise ValidationError("An operation can have at most 16 parameters.")
        if any(
            type(item) not in (str, int, bool) or len(key) > 64 or len(str(item)) > 500
            for key, item in value.items()
        ):
            raise ValidationError("Parameters must have scalar string, integer or boolean values.")
        return value


class BatchRequestSerializer(serializers.Serializer):
    requests = BatchCallSerializer(many=True, allow_empty=False, max_length=25)

    def validate_requests(self, calls):
        if len({call["id"] for call in calls}) != len(calls):
            raise ValidationError("Operation IDs must be unique within a batch.")
        return calls


class BatchResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.IntegerField()
    body = serializers.JSONField()


class BatchResponseSerializer(serializers.Serializer):
    results = BatchResultSerializer(many=True)


def dispatch(request, path, query):
    endpoint = resolve(path)
    callback = endpoint.func
    kwargs = {
        **callback.initkwargs,
        "authentication_classes": (BatchAuthentication,),
        "throttle_classes": (),
    }
    view = callback.cls.as_view(callback.actions, **kwargs) if hasattr(
        callback, "actions",
    ) else callback.cls.as_view(**kwargs)

    subrequest = copy(request._request)
    subrequest.method = "GET"
    subrequest.path = path
    subrequest.path_info = path
    subrequest.GET = query
    subrequest.META = {**subrequest.META, "QUERY_STRING": query.urlencode()}
    subrequest.resolver_match = endpoint
    subrequest.batch_identity = (request.user, request.auth)
    try:
        response = view(subrequest, **endpoint.kwargs)
    except Http404:
        return 404, problem(404)
    except Exception:
        logger.exception("Catalog batch operation failed: %s", endpoint.url_name)
        return 500, problem(500)
    return response.status_code, response.data


class BatchView(V3ContractMixin, APIView):
    @extend_schema(request=BatchRequestSerializer, responses=BatchResponseSerializer)
    def post(self, request):
        serializer = BatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        calls = serializer.validated_data["requests"]
        # DRF charges one request in initial(). Charge the remaining operations before dispatch.
        for _ in calls[1:]:
            self.check_throttles(request)

        results = []
        completed = {}
        for call in calls:
            status, body = self.execute_call(request, call, completed)
            results.append({"id": call["id"], "status": status, "body": body})
        return Response({"results": results})

    def execute_call(self, request, call, completed):
        route = BATCH_OPERATIONS.get(call["operation"])
        if route is None:
            return 400, problem(400, code="unknown_operation", detail="The operation is unavailable in batch.")
        name, needs_pk = route
        params = call["params"].copy()
        lookup = {"pk": params.pop("pk", "")} if needs_pk else {}
        try:
            path = urlsplit(reverse(name, kwargs=lookup)).path
        except NoReverseMatch:
            return 400, problem(400, code="invalid_id", detail="A positive integer pk is required.")
        query = QueryDict(mutable=True)
        for key, value in sorted(params.items()):
            query[key] = str(value)
        cache_key = (path, query.urlencode())
        if cache_key not in completed:
            completed[cache_key] = dispatch(request, path, query)
        return completed[cache_key]
