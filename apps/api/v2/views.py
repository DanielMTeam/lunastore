import time
import uuid
import json

import jwt
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes, inline_serializer
from apps.marketplace.models import Application, Category, Collection, Distribution
from apps.marketplace.serializers import ApplicationSerializer, CategorySerializer, CollectionSerializer, DistributionSerializer
from apps.user.models import User
from apps.user.serializers import UserSerializer
from apps.core.notifications.services import NotificationService
from apps.core.search import SearchService, SearchUnavailableError

from apps.api.constants import ErrorCodes, PUB_UPLOAD_POLICIES, ALLOWED_MIMES
from apps.api.exceptions import LunaException

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import CustomTokenObtainPairSerializer


@extend_schema_view(
    post=extend_schema(summary="get JWT access and refresh tokens (supports 2FA)"),
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema_view(
    post=extend_schema(summary="refresh JWT access token"),
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


class V2Pagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


@extend_schema_view(
    list=extend_schema(summary="get paginated list of users"),
    retrieve=extend_schema(summary="get detailed user profile"),
)
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer

    @extend_schema(
        summary="get public upload token",
        description="Returns public upload token",
        parameters=[
            OpenApiParameter(name="target", description="Target object (avatar, icon, screenshot)", required=True, type=str, location=OpenApiParameter.QUERY)
        ],
    )
    @action(detail=False, methods=["get"], url_path="getPublicUploadToken", permission_classes=[IsAuthenticated])
    def get_public_upload_token(self, request):
        target = request.query_params.get("target")

        if not target or target not in PUB_UPLOAD_POLICIES:
            return Response({"error": "Invalid target"}, status=400)

        policy = PUB_UPLOAD_POLICIES[target]
        guard_phrase = str(uuid.uuid4().hex)[:8]

        cache_key = f"cdn_guard_{request.user.id}_{guard_phrase}"
        cache.set(cache_key, True, timeout=3600)

        current_time = int(time.time())

        payload = {
            "type": "cdn-upload",
            "object": policy["obj"],
            "user": str(request.user.id),
            "guard": guard_phrase,
            "mode": "public",
            "accept": policy["mimes"],
            "iat": current_time,
            "exp": current_time + 3600,
            "img_opts": {"mw": policy["mw"], "mh": policy["mh"]},
        }

        upload_token = jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256")
        return Response({"upload_token": upload_token, "guard": guard_phrase})

    @extend_schema(
        summary="get private upload token",
        description="Returns private upload token",
        parameters=[
            OpenApiParameter(name="target", description="Target", required=False, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="app_id", description="Application ID", required=True, type=int, location=OpenApiParameter.QUERY)
        ],
    )
    @action(detail=False, methods=["get"], url_path="getPrivateUploadToken", permission_classes=[IsAuthenticated])
    def get_private_upload_token(self, request):
        target = request.query_params.get("target", "distribution")
        app_id = request.query_params.get("app_id")

        if not app_id or not app_id.isdigit():
            return Response({"error": "app_id is required and must be an integer"}, status=400)

        app_obj = get_object_or_404(Application, id=app_id)
        if app_obj.user != request.user and not request.user.is_staff:
            return Response({"error": "Not your app"}, status=403)

        guard_phrase = str(uuid.uuid4().hex)[:8]

        cache_key = f"cdn_guard_{request.user.id}_{guard_phrase}"
        cache.set(cache_key, True, timeout=3600)

        current_time = int(time.time())

        payload = {
            "type": "cdn-upload",
            "object": str(app_obj.id),
            "user": str(request.user.id),
            "guard": guard_phrase,
            "mode": "private",
            "accept": ALLOWED_MIMES,
            "iat": current_time,
            "exp": current_time + 3600,
        }

        upload_token = jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256")
        return Response({"upload_token": upload_token, "guard": guard_phrase})

    @action(detail=False, methods=["get"], url_path="getNotificationToken", permission_classes=[IsAuthenticated])
    def get_notification_token(self, request):
        token = NotificationService.get_receive_token(request.user.id)
        return Response({
            "token": token,
            "ws_url": getattr(request, 'geo_domains', {}).get('SPIRE_URL', settings.LUNASPIRE_URL)
        })

    @extend_schema(
        summary="search users",
        description="Returns paginated list of users matching the query",
        parameters=[
            OpenApiParameter(
                name="query",
                description="Search query",
                required=True,
                type=str,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("query")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)
        paginator = self.pagination_class()
        limit = paginator.get_limit(request)
        offset = paginator.get_offset(request)
        try:
            user_ids, total = SearchService.search_user_ids(query, limit=limit, offset=offset)
        except SearchUnavailableError:
            return Response({"error": "Search service unavailable"}, status=503)
        results = SearchService.order_queryset_by_ids(self.get_queryset(), user_ids)
        serializer = self.get_serializer(results, many=True)
        paginator.request = request
        paginator.count = total
        return paginator.get_paginated_response(serializer.data)


@extend_schema_view(
    list=extend_schema(summary="get paginated list of applications"),
    retrieve=extend_schema(summary="get detailed application info"),
)
class MarketplaceViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        return Application.objects.filter(is_private=False, is_under_dmca=False)
    serializer_class = ApplicationSerializer
    pagination_class = V2Pagination

    def get_object(self):
        obj = super().get_object()
        if obj.is_under_dmca:
            raise LunaException(
                code=ErrorCodes.APPLICATION_IS_UNDER_DMCA,
                message=f"Application (id: {obj.id}) unavailable because his creators/uploaders received a DMCA strike",
                status_code=403,
            )
        if obj.is_private:
            raise LunaException(
                code=ErrorCodes.APPLICATION_PRIVATE,
                message=f"Application (id: {obj.id}) unavailable because it is private",
                status_code=403,
            )
        return obj

    @extend_schema(
        summary="search applications",
        description="Returns paginated list of applications matching the query",
        parameters=[
            OpenApiParameter(name="query", description="Search query", required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="category", description="Category ID filter", required=False, type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="author", description="Author user ID filter", required=False, type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="is_free", description="Only free apps (true/on/1)", required=False, type=str, location=OpenApiParameter.QUERY),
        ],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("query")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        category_id = request.query_params.get("category")
        author_id = request.query_params.get("author")
        is_free = request.query_params.get("is_free", "").lower() in ("1", "true", "on", "yes")
        paginator = self.pagination_class()
        limit = paginator.get_limit(request)
        offset = paginator.get_offset(request)

        try:
            app_ids, total = SearchService.search_application_ids(
                query,
                limit=limit,
                offset=offset,
                category_id=category_id,
                author_id=author_id,
                is_free=is_free,
            )
        except SearchUnavailableError:
            return Response({"error": "Search service unavailable"}, status=503)

        results = SearchService.order_queryset_by_ids(self.get_queryset(), app_ids)
        serializer = self.get_serializer(results, many=True)
        paginator.request = request
        paginator.count = total
        return paginator.get_paginated_response(serializer.data)


class SearchSuggestView(APIView):
    @extend_schema(
        summary="search suggest (typeahead)",
        description="Returns lightweight app and user suggestions for a query",
        parameters=[
            OpenApiParameter(name="query", description="Search query", required=True, type=str),
            OpenApiParameter(name="limit", description="Max results per type", required=False, type=int),
            OpenApiParameter(
                name="type",
                description="all, apps, or users",
                required=False,
                type=str,
            ),
        ],
    )
    def get(self, request):
        query = (request.query_params.get("query") or "").strip()
        if len(query) < 2:
            return Response({"apps": [], "users": []})
        try:
            limit = int(request.query_params.get("limit", "8"))
        except (TypeError, ValueError):
            limit = 8
        limit = max(1, min(limit, 20))
        search_type = request.query_params.get("type", "all")
        if search_type not in ("all", "apps", "users"):
            search_type = "all"
        try:
            data = SearchService.suggest(query, limit=limit, search_type=search_type)
        except SearchUnavailableError:
            return Response({"error": "Search service unavailable"}, status=503)
        return Response(data)


@extend_schema_view(
    list=extend_schema(summary="get all application categories"),
    retrieve=extend_schema(summary="get detailed category info"),
)
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter()
    serializer_class = CategorySerializer
    pagination_class = V2Pagination

    @extend_schema(
        summary="get apps by category",
        description="Returns paginated apps in a given category",
    )
    @action(detail=True, methods=["get"], url_path="apps")
    def apps(self, request, pk=None):
        category = self.get_object()
        apps = Application.objects.filter(categories=category).exclude(is_private=True).order_by("-published")
        page = self.paginate_queryset(apps)
        if page is not None:
            serializer = ApplicationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ApplicationSerializer(apps, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(summary="get all distributions/builds"),
    retrieve=extend_schema(summary="get detailed distribution info"),
)
class DistributionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DistributionSerializer
    pagination_class = V2Pagination

    def get_queryset(self):
        # hide private app distributions unless requester is the owner
        qs = Distribution.objects.select_related("app", "app__user")
        user = self.request.user
        if user.is_authenticated:
            return qs.filter(Q(app__is_private=False) | Q(app__user=user))
        return qs.filter(app__is_private=False)

    @extend_schema(
        summary="get distributions by application",
        parameters=[
            OpenApiParameter(name="app_id", description="Application ID", required=True, type=int, location=OpenApiParameter.QUERY)
        ],
    )
    @action(detail=False, methods=["get"], url_path="by_app")
    def by_app(self, request):
        app_id = request.query_params.get("app_id")
        if not app_id:
            return Response({"error": "app_id is required"}, status=400)

        app = get_object_or_404(Application, pk=app_id)
        if app.is_private and (
                not request.user.is_authenticated or app.user_id != request.user.id):
            raise LunaException(
                code=ErrorCodes.APPLICATION_PRIVATE,
                message=f"Application (id: {app.id}) unavailable because it is private",
                status_code=403,
            )

        distributions = self.get_queryset().filter(app=app)
        page = self.paginate_queryset(distributions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(distributions, many=True)
        return Response(serializer.data)


class ServiceViewSet(viewsets.ViewSet):
    def get_throttles(self) -> list:
        # uptime monitors hit this every minute; do not burn anon daily quota
        if self.action == "heartbeat":
            return []
        return super().get_throttles()

    @extend_schema(summary="check API status")
    @action(detail=False, methods=["get"], url_path="heartbeat")
    def heartbeat(self, request):
        return Response({"status": "ok", "timestamp": timezone.now(), "version": settings.VERSION})

    @extend_schema(summary="returns list of LunaStore developers")
    @action(detail=False, methods=["get"], url_path="developersList")
    def developers(self, request):
        return Response({
            "creator": "Daniel Myslivets",
            "backend": "fayzetwin, notsecret808, zazios, synzr, filldor",
            "frontend": "Daniel Myslivets, fayzetwin",
            "system-administration": "eversiege, thefoxmilya, rotama",
            "design": "chelka0, Daniel Myslivets",
            "special_thanks": "MondySpartan (logo), nocha3 (native client of LunaStore for Windows XP)",
        })

    @extend_schema(summary="returns one cool thing")
    @action(detail=False, methods=["get"], url_path="kunyakin")
    def kunyakin(self, request):
        return Response({"answer": "влад кунякин пробудил шаринган"})


@extend_schema_view(
    list=extend_schema(summary="get public collections"),
    retrieve=extend_schema(summary="get detailed collection info"),
)
class CollectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CollectionSerializer
    pagination_class = V2Pagination

    def get_queryset(self):
        qs = Collection.objects.select_related("owner").order_by("-updated_at")
        if getattr(self, "action", None) in ("list", "by_user"):
            user = self.request.user
            if user.is_authenticated and getattr(self, "action", None) == "list":
                return qs.filter(Q(is_public=True) | Q(owner=user))
            if getattr(self, "action", None) == "list":
                return qs.filter(is_public=True)
        return qs

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        if not obj.is_public and (not user.is_authenticated or user.id != obj.owner_id):
            raise LunaException(
                code=ErrorCodes.COLLECTION_PRIVATE,
                message=f"Collection (id: {obj.id}) is private",
                status_code=403,
            )
        return obj

    @extend_schema(
        summary="get apps in collection",
        description="Returns paginated apps in a given collection",
    )
    @action(detail=True, methods=["get"], url_path="apps")
    def apps(self, request, pk=None):
        collection = self.get_object()
        app_ids = collection.items.order_by("-added_at").values_list(
            "application_id", flat=True
        )
        apps = Application.objects.filter(id__in=app_ids).exclude(is_private=True)
        # preserve collection order
        app_map = {app.id: app for app in apps}
        ordered = [app_map[i] for i in app_ids if i in app_map]
        page = self.paginate_queryset(ordered)
        if page is not None:
            serializer = ApplicationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ApplicationSerializer(ordered, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="get collections by user",
        description="Returns public collections owned by user_id",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="Owner user id",
                required=True,
                type=int,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="by_user")
    def by_user(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "user_id parameter is required"}, status=400)
        qs = Collection.objects.filter(owner_id=user_id, is_public=True).select_related(
            "owner"
        ).order_by("-updated_at")
        requester = request.user
        if requester.is_authenticated and str(requester.id) == str(user_id):
            qs = Collection.objects.filter(owner_id=user_id).select_related(
                "owner"
            ).order_by("-updated_at")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class ExecuteView(APIView):
    @extend_schema(
        summary="Batch API execution",
        description="""
        VK-like execute method for batch API requests (～￣▽￣)～

        Доступные методы и их назначение:
        - `user.list`: Получение списка всех пользователей (пагинировано). Зачем: для админки или списков.
        - `user.retrieve`: Получить инфу об одном пользователе (параметр `pk`). Зачем: профиль пользователя.
        - `marketplace.list`: Список всех приложений в магазине. Зачем: главная страница или лента.
        - `marketplace.retrieve`: Детали одного приложения (параметр `pk`). Зачем: страница приложения.
        - `user.search`: Поиск пользователей (параметр `query`). Зачем: строка поиска пользователей.
        - `marketplace.search`: Поиск приложений (параметр `query`). Зачем: строка поиска.
        - `category.list`: Список всех категорий. Зачем: боковое меню или фильтры.
        - `category.retrieve`: Детали категории (параметр `pk`). Зачем: заголовок страницы категории.
        - `category.apps`: Приложения внутри конкретной категории (параметр `pk`). Зачем: просмотр раздела (например, 'Игры').
        - `distribution.list`: Список всех сборок/дистрибутивов вообще. Зачем: техническая статистика.
        - `distribution.retrieve`: Детали одной сборки (параметр `pk`). Зачем: перед скачиванием.
        - `distribution.by_app`: Сборки конкретного приложения (параметр `app_id`). Зачем: вкладка 'Версии' на странице приложения.
        - `collection.list`: Список публичных коллекций. Зачем: каталог коллекций.
        - `collection.retrieve`: Детали коллекции (параметр `pk`). Зачем: страница коллекции.
        - `collection.apps`: Приложения в коллекции (параметр `pk`). Зачем: содержимое коллекции.
        - `collection.by_user`: Коллекции пользователя (параметр `user_id`). Зачем: профиль.
        """
    )
    def post(self, request):
        code = request.data.get("code", [])
        if not isinstance(code, list):
            return Response({"error": "Invalid format, 'code' must be a list of calls"}, status=400)

        if len(code) > 25:
            return Response({"error": "Batch size limit exceeded. Maximum 25 calls per request."}, status=400)

        from django.urls import resolve
        from rest_framework.request import Request
        import copy

        responses = []

        for call in code:
            method_name = call.get("method")
            params = call.get("params", {})

            if not method_name:
                responses.append({
                    "status": "error",
                    "message": "method missing in call",
                    "error_code": ErrorCodes.METHOD_NOT_FOUND
                })
                continue

            # Internal mapping for V2 execute routing
            # For simplicity in this implementation, we will explicitly route allowed methods
            # user.retrieve, marketplace.retrieve, marketplace.search, category.apps, etc.

            # Map method string to ViewSet and action
            view_mapping = {
                "user.list": (UserViewSet, "list"),
                "user.retrieve": (UserViewSet, "retrieve"),
                "user.search": (UserViewSet, "search"),
                "marketplace.list": (MarketplaceViewSet, "list"),
                "marketplace.retrieve": (MarketplaceViewSet, "retrieve"),
                "marketplace.search": (MarketplaceViewSet, "search"),
                "category.list": (CategoryViewSet, "list"),
                "category.retrieve": (CategoryViewSet, "retrieve"),
                "category.apps": (CategoryViewSet, "apps"),
                "distribution.list": (DistributionViewSet, "list"),
                "distribution.retrieve": (DistributionViewSet, "retrieve"),
                "distribution.by_app": (DistributionViewSet, "by_app"),
                "collection.list": (CollectionViewSet, "list"),
                "collection.retrieve": (CollectionViewSet, "retrieve"),
                "collection.apps": (CollectionViewSet, "apps"),
                "collection.by_user": (CollectionViewSet, "by_user"),
            }

            if method_name not in view_mapping:
                responses.append({
                    "status": "error",
                    "message": f"Method {method_name} not allowed or unknown",
                    "error_code": ErrorCodes.METHOD_NOT_FOUND
                })
                continue

            viewset_class, action_name = view_mapping[method_name]

            # Create a mock request for the viewset
            mock_request = copy.copy(request._request)
            mock_request.GET = mock_request.GET.copy()
            mock_request.GET.update(params)

            view = viewset_class.as_view({
                'get': action_name,
                'post': action_name
            })

            # extract kwargs like 'pk'
            kwargs = {}
            if 'pk' in params:
                kwargs['pk'] = params['pk']

            try:
                # Need to wrap mock_request in DRF Request to be safe
                response = view(mock_request, **kwargs)
                response.render()
                responses.append(json.loads(response.content.decode('utf-8')))
            except Exception as e:
                import logging
                logging.error(f"Error in execute method {method_name}: {str(e)}", exc_info=True)
                from apps.api.handlers import luna_exception_handler
                err_response = luna_exception_handler(e, None)
                if err_response is not None:
                    err_response.render()
                    responses.append(json.loads(err_response.content.decode('utf-8')))
                else:
                    responses.append({
                        "status": "error",
                        "message": "Internal server error",
                        "error_code": ErrorCodes.UNKNOWN_ERROR
                    })

        return Response({"responses": responses})
