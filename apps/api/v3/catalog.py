from functools import partial

from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.cache import add_never_cache_headers
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.catalog import (
    APILimitOffsetPagination, application_queryset, distribution_queryset, paginated_search, with_application_cards,
)
from apps.api.media import absolute_media_url
from apps.core.search import SearchService, SearchUnavailableError
from apps.core.search.service import is_query_too_short
from apps.marketplace.models import Category, Collection, CollectionItem, Platform
from apps.marketplace.services.visibility import public_app_filter
from apps.marketplace.views import serve_distribution_download
from apps.user.models import User

from .contract import SearchUnavailable, V3ContractMixin
from .serializers import (
    ApplicationParams, ApplicationSerializer, CategorySerializer, CollectionParams, CollectionSerializer,
    DistributionSerializer, HealthSerializer, PageParams, PlatformSerializer, SuggestionParams,
    SuggestionSerializer, UserParams, UserSerializer,
)


def validated_query(serializer, request):
    params = serializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    return params.validated_data


class CatalogPagination(APILimitOffsetPagination):
    params = None

    def get_limit(self, request):
        return (self.params or {}).get("limit", self.default_limit)

    def get_offset(self, request):
        return (self.params or {}).get("offset", 0)


@extend_schema_view(list=extend_schema(parameters=[PageParams]))
class CatalogViewSet(V3ContractMixin, viewsets.ReadOnlyModelViewSet):
    pagination_class = CatalogPagination
    lookup_value_regex = r"[0-9]{1,19}"
    query_serializer = PageParams

    def validate_query(self, request, serializer=None):
        self.params = validated_query(serializer or self.query_serializer, request)
        self.paginator.params = self.params
        return self.params

    def list(self, request, *args, **kwargs):
        self.validate_query(request)
        return super().list(request, *args, **kwargs)

    def serialize_page(self, queryset, serializer):
        page = self.paginate_queryset(queryset)
        data = serializer(page, many=True, context=self.get_serializer_context()).data
        return self.get_paginated_response(data)

    def search_page(self, queryset, search):
        try:
            return paginated_search(self, self.request, queryset, search)
        except SearchUnavailableError as exc:
            raise SearchUnavailable() from exc


@extend_schema_view(
    list=extend_schema(operation_id="v3_apps_list", parameters=[ApplicationParams]),
    retrieve=extend_schema(operation_id="v3_apps_retrieve"),
)
class ApplicationViewSet(CatalogViewSet):
    serializer_class = ApplicationSerializer
    query_serializer = ApplicationParams

    def get_queryset(self):
        queryset = application_queryset(self.request.user, include_private=self.action == "retrieve")
        return with_application_cards(queryset).order_by("-published", "-pk")

    def list(self, request, *args, **kwargs):
        params = self.validate_query(request)
        platform = get_object_or_404(Platform, code=params["platform"]) if "platform" in params else None
        filters = {
            "category_id": params.get("category"),
            "author_id": params.get("author"),
            "platform_id": platform.pk if platform else None,
            "is_free": params["is_free"],
        }
        queryset = self.get_queryset()
        if filters["category_id"]:
            queryset = queryset.filter(categories=filters["category_id"])
        if filters["author_id"]:
            queryset = queryset.filter(user_id=filters["author_id"])
        if platform:
            queryset = queryset.filter(platforms=platform)
        if filters["is_free"]:
            queryset = queryset.filter(price=0)
        if "q" in params:
            search = partial(SearchService.search_application_ids, params["q"], **filters)
            return self.search_page(queryset, search)
        return self.serialize_page(queryset, self.get_serializer_class())

    @extend_schema(
        operation_id="v3_apps_distributions_list",
        parameters=[PageParams],
        responses=DistributionSerializer(many=True),
    )
    @action(detail=True)
    def distributions(self, request, pk=None):
        self.validate_query(request, PageParams)
        app = get_object_or_404(application_queryset(request.user, include_private=True), pk=pk)
        distributions = distribution_queryset(request.user).filter(app=app).order_by("-published", "-pk")
        return self.serialize_page(distributions, DistributionSerializer)


@extend_schema_view(
    list=extend_schema(operation_id="v3_users_list", parameters=[UserParams]),
    retrieve=extend_schema(operation_id="v3_users_retrieve"),
)
class UserViewSet(CatalogViewSet):
    queryset = User.objects.filter(is_active=True).order_by("pk")
    serializer_class = UserSerializer
    query_serializer = UserParams

    def list(self, request, *args, **kwargs):
        params = self.validate_query(request)
        if "q" in params:
            return self.search_page(self.get_queryset(), partial(SearchService.search_user_ids, params["q"]))
        return self.serialize_page(self.get_queryset(), self.get_serializer_class())


class CategoryAppsParams(PageParams):
    platform = serializers.SlugField(required=False, max_length=64)


@extend_schema_view(
    list=extend_schema(operation_id="v3_categories_list"),
    retrieve=extend_schema(operation_id="v3_categories_retrieve"),
)
class CategoryViewSet(CatalogViewSet):
    queryset = Category.objects.order_by("name", "pk")
    serializer_class = CategorySerializer

    @extend_schema(
        operation_id="v3_categories_apps_list",
        parameters=[CategoryAppsParams],
        responses=ApplicationSerializer(many=True),
    )
    @action(detail=True)
    def apps(self, request, pk=None):
        params = self.validate_query(request, CategoryAppsParams)
        apps = application_queryset(request.user).filter(categories=self.get_object())
        if "platform" in params:
            apps = apps.filter(platforms=get_object_or_404(Platform, code=params["platform"]))
        return self.serialize_page(with_application_cards(apps).order_by("-published", "-pk"), ApplicationSerializer)


@extend_schema_view(
    list=extend_schema(operation_id="v3_distributions_list"),
    retrieve=extend_schema(operation_id="v3_distributions_retrieve"),
)
class DistributionViewSet(CatalogViewSet):
    serializer_class = DistributionSerializer

    def get_queryset(self):
        return distribution_queryset(self.request.user).order_by("app_id", "-published", "-pk")

    @extend_schema(responses={302: None})
    @action(detail=True)
    def download(self, request, pk=None):
        distribution = self.get_object()
        if not distribution.has_download:
            raise Http404
        response = serve_distribution_download(request, distribution, legacy_transport=False)
        add_never_cache_headers(response)
        return response


@extend_schema_view(
    list=extend_schema(operation_id="v3_platforms_list"),
    retrieve=extend_schema(operation_id="v3_platforms_retrieve"),
)
class PlatformViewSet(CatalogViewSet):
    queryset = Platform.objects.order_by("name", "pk")
    serializer_class = PlatformSerializer


@extend_schema_view(
    list=extend_schema(operation_id="v3_collections_list", parameters=[CollectionParams]),
    retrieve=extend_schema(operation_id="v3_collections_retrieve"),
)
class CollectionViewSet(CatalogViewSet):
    serializer_class = CollectionSerializer
    query_serializer = CollectionParams

    def get_queryset(self):
        visible_items = CollectionItem.objects.filter(public_app_filter("application__")).select_related(
            "application",
        ).order_by("-added_at", "-pk")[:4]
        queryset = Collection.objects.select_related("owner").annotate(
            items_count=Count("items", filter=public_app_filter("items__application__")),
        ).prefetch_related(Prefetch("items", queryset=visible_items, to_attr="visible_icon_items")).order_by(
            "-updated_at", "-pk",
        )
        visibility = Q(is_public=True)
        if self.request.user.is_authenticated:
            visibility |= Q(owner=self.request.user)
        queryset = queryset.filter(visibility)
        user_id = getattr(self, "params", {}).get("user_id")
        if user_id is not None:
            queryset = queryset.filter(owner_id=user_id)
        return queryset

    @extend_schema(
        operation_id="v3_collections_apps_list",
        parameters=[PageParams],
        responses=ApplicationSerializer(many=True),
    )
    @action(detail=True)
    def apps(self, request, pk=None):
        self.validate_query(request, PageParams)
        apps = application_queryset(request.user).filter(collection_items__collection=self.get_object())
        apps = with_application_cards(apps).order_by("-collection_items__added_at", "-pk")
        return self.serialize_page(apps, ApplicationSerializer)


class SuggestionView(V3ContractMixin, APIView):
    @extend_schema(
        operation_id="v3_search_suggestions_retrieve",
        parameters=[SuggestionParams],
        responses=SuggestionSerializer,
    )
    def get(self, request):
        params = validated_query(SuggestionParams, request)
        if is_query_too_short(params["q"]):
            return Response({"apps": [], "users": []})
        try:
            data = SearchService.suggest(params["q"], limit=params["limit"], search_type=params["type"])
        except SearchUnavailableError as exc:
            raise SearchUnavailable() from exc
        for app in data["apps"]:
            app["icon_url"] = absolute_media_url(app["icon_url"])
        for user in data["users"]:
            user["avatar_url"] = absolute_media_url(user["avatar_url"])
        return Response(SuggestionSerializer(data).data)


class HealthView(V3ContractMixin, APIView):
    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()

    @extend_schema(responses=HealthSerializer)
    def get(self, request):
        return Response({"status": "ok"})
