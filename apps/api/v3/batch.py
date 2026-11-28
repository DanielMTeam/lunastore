import logging
from io import BytesIO
from time import monotonic
from typing import NamedTuple

from django.db import OperationalError, connection, transaction
from django.http import QueryDict
from django.urls import NoReverseMatch, reverse
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, serializers
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.search.client import search_timeout

from . import catalog
from .contract import V3ContractMixin, problem, v3_exception_handler


logger = logging.getLogger(__name__)
MAX_BATCH_BYTES = 64 * 1024
MAX_BATCH_SEARCHES = 2
BATCH_SECONDS = 8
STATEMENT_TIMEOUT_MS = 1000


class CatalogOperation(NamedTuple):
    view: type
    action: str
    route: str
    detail: bool = False
    searchable: bool = False


# Allow only read operations with the same querysets and object checks as direct GET.
BATCH_OPERATIONS = {
    "v3_apps_list": CatalogOperation(catalog.ApplicationViewSet, "list", "v3-app-list", searchable=True),
    "v3_apps_retrieve": CatalogOperation(catalog.ApplicationViewSet, "retrieve", "v3-app-detail", True),
    "v3_apps_distributions_list": CatalogOperation(catalog.ApplicationViewSet, "distributions", "v3-app-distributions", True),
    "v3_categories_list": CatalogOperation(catalog.CategoryViewSet, "list", "v3-category-list"),
    "v3_categories_retrieve": CatalogOperation(catalog.CategoryViewSet, "retrieve", "v3-category-detail", True),
    "v3_categories_apps_list": CatalogOperation(catalog.CategoryViewSet, "apps", "v3-category-apps", True),
    "v3_collections_list": CatalogOperation(catalog.CollectionViewSet, "list", "v3-collection-list"),
    "v3_collections_retrieve": CatalogOperation(catalog.CollectionViewSet, "retrieve", "v3-collection-detail", True),
    "v3_collections_apps_list": CatalogOperation(catalog.CollectionViewSet, "apps", "v3-collection-apps", True),
    "v3_distributions_list": CatalogOperation(catalog.DistributionViewSet, "list", "v3-distribution-list"),
    "v3_distributions_retrieve": CatalogOperation(catalog.DistributionViewSet, "retrieve", "v3-distribution-detail", True),
    "v3_platforms_list": CatalogOperation(catalog.PlatformViewSet, "list", "v3-platform-list"),
    "v3_platforms_retrieve": CatalogOperation(catalog.PlatformViewSet, "retrieve", "v3-platform-detail", True),
    "v3_users_list": CatalogOperation(catalog.UserViewSet, "list", "v3-user-list", searchable=True),
    "v3_users_retrieve": CatalogOperation(catalog.UserViewSet, "retrieve", "v3-user-detail", True),
    "v3_search_suggestions_retrieve": CatalogOperation(catalog.SuggestionView, "get", "v3-suggestions", searchable=True),
}


class BatchTooLarge(exceptions.APIException):
    status_code = 413
    default_code = "batch_too_large"
    default_detail = "A batch body may contain at most 64 KiB."


class BatchDeadlineExceeded(exceptions.APIException):
    status_code = 503
    default_code = "batch_timeout"
    default_detail = "The batch execution time limit was reached."


class BatchJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        body = stream.read(MAX_BATCH_BYTES + 1)
        if len(body) > MAX_BATCH_BYTES:
            raise BatchTooLarge()
        try:
            return super().parse(BytesIO(body), media_type, parser_context)
        except RecursionError as exc:
            raise exceptions.ParseError("Batch JSON is nested too deeply.") from exc


class BatchCallSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=64)
    operation = serializers.CharField(max_length=100)
    params = serializers.DictField(required=False, default=dict)

    def validate_params(self, value):
        if len(value) > 16:
            raise exceptions.ValidationError("An operation can have at most 16 parameters.")
        if any(
            type(item) not in (str, int, bool) or len(key) > 64 or len(str(item)) > 500
            for key, item in value.items()
        ):
            raise exceptions.ValidationError("Parameters must have scalar string, integer or boolean values.")
        return value


class BatchRequestSerializer(serializers.Serializer):
    requests = BatchCallSerializer(many=True, allow_empty=False, max_length=25)

    def validate_requests(self, calls):
        if len({call["id"] for call in calls}) != len(calls):
            raise exceptions.ValidationError("Operation IDs must be unique within a batch.")
        return calls


class BatchResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.IntegerField()
    body = serializers.JSONField()


class BatchResponseSerializer(serializers.Serializer):
    results = BatchResultSerializer(many=True)


class CatalogReadRequest:
    """Carry the authenticated principal and URL context into a shared read handler."""

    method = "GET"

    def __init__(self, request, path, query):
        self.user = request.user
        self.auth = request.auth
        self.authenticators = request.authenticators
        self.successful_authenticator = request.successful_authenticator
        self.query_params = self.GET = query
        self.path = path
        self._absolute_url = request.build_absolute_uri

    def build_absolute_uri(self, location=None):
        if location is None:
            query = self.query_params.urlencode()
            location = f"{self.path}?{query}" if query else self.path
        return self._absolute_url(location)


def check_deadline(deadline):
    if monotonic() >= deadline:
        raise BatchDeadlineExceeded()


def run_catalog_read(operation, request, lookup, deadline):
    view = operation.view()
    view.setup(request, **lookup)
    view.action = operation.action
    view.format_kwarg = None

    def check_query(execute, sql, params, many, context):
        check_deadline(deadline)
        return execute(sql, params, many, context)

    try:
        check_deadline(deadline)
        nested = connection.in_atomic_block
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT setting FROM pg_settings WHERE name = 'statement_timeout'")
                previous = int(cursor.fetchone()[0])
                timeout = min(previous or STATEMENT_TIMEOUT_MS, STATEMENT_TIMEOUT_MS)
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(timeout)])
            with connection.execute_wrapper(check_query), search_timeout(2):
                view.check_permissions(request)
                response = getattr(view, operation.action)(request, **lookup)
                check_deadline(deadline)
            # SET LOCAL persists through a successful savepoint in an outer transaction.
            if nested:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(previous)])
            return response.status_code, response.data
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) != "57014":
            logger.exception("Catalog batch operation failed: %s", operation.route)
            return 500, problem(500)
        error = BatchDeadlineExceeded()
    except Exception as exc:
        error = exc
    response = v3_exception_handler(error, {"request": request, "view": view})
    if response is not None:
        return response.status_code, response.data
    logger.error("Catalog batch operation failed: %s", operation.route, exc_info=error)
    return 500, problem(500)


class BatchView(V3ContractMixin, APIView):
    parser_classes = (BatchJSONParser,)

    @extend_schema(
        description="Accepts up to 64 KiB of JSON, 25 read operations and two distinct searches.",
        request=BatchRequestSerializer,
        responses=BatchResponseSerializer,
    )
    def post(self, request):
        serializer = BatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        calls = serializer.validated_data["requests"]
        deadline = monotonic() + BATCH_SECONDS
        # Initial DRF throttling charges the first item.
        for _ in calls[1:]:
            check_deadline(deadline)
            self.check_throttles(request)

        results = []
        completed = {}
        searches = set()
        for call in calls:
            operation = BATCH_OPERATIONS.get(call["operation"])
            if operation is None:
                status, body = 400, problem(400, code="unknown_operation", detail="The operation is unavailable in batch.")
            else:
                status, body = self.execute_call(request, operation, call["params"], completed, deadline, searches)
            results.append({"id": call["id"], "status": status, "body": body})
        return Response({"results": results})

    def execute_call(self, request, operation, params, completed, deadline, searches):
        params = params.copy()
        lookup = {"pk": params.pop("pk", "")} if operation.detail else {}
        try:
            path = reverse(operation.route, kwargs=lookup)
        except NoReverseMatch:
            return 400, problem(400, code="invalid_id", detail="A positive integer pk is required.")

        query = QueryDict(mutable=True)
        for key, value in sorted(params.items()):
            query[key] = str(value)
        cache_key = (path, query.urlencode())
        if cache_key not in completed:
            if monotonic() >= deadline:
                error = BatchDeadlineExceeded()
                return error.status_code, problem(error.status_code, code=error.default_code,
                                                  detail=error.default_detail)
            if operation.searchable and "q" in query:
                if len(searches) >= MAX_BATCH_SEARCHES:
                    return 400, problem(400, code="batch_search_limit", detail="Too many distinct searches.")
                searches.add(cache_key)
            catalog_request = CatalogReadRequest(request, path, query)
            completed[cache_key] = run_catalog_read(operation, catalog_request, lookup, deadline)
        return completed[cache_key]
