import time
import uuid
import json

import jwt
from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
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
from apps.marketplace.models import Application, Category, Distribution
from apps.marketplace.serializers import ApplicationSerializer, CategorySerializer, DistributionSerializer
from apps.user.models import User
from apps.user.serializers import UserSerializer
from apps.core.notifications.services import NotificationService

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


@extend_schema_view(
    list=extend_schema(summary="get paginated list of applications"),
    retrieve=extend_schema(summary="get detailed application info"),
)
class MarketplaceViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        return Application.objects.exclude(is_private=True)
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
            OpenApiParameter(name="query", description="Search query", required=True, type=str, location=OpenApiParameter.QUERY)
        ],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("query")
        if not query:
            return Response({"error": "Query parameter is required"}, status=400)

        results = (
            Application.objects.annotate(
                similarity=TrigramSimilarity("title", query)
                + TrigramSimilarity("description", query)
                + TrigramSimilarity("slogan", query),
            )
            .filter(similarity__gt=0.1)
            .exclude(is_private=True)
            .order_by("-similarity")
        )
        page = self.paginate_queryset(results)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(results, many=True)
        return Response(serializer.data)


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
    queryset = Distribution.objects.filter()
    serializer_class = DistributionSerializer
    pagination_class = V2Pagination

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
        if app.is_private:
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


class ExecuteView(APIView):
    """
    VK-like execute method for batch API requests (～￣▽￣)～
    """

    @extend_schema(
        summary="Batch API execution",
        description="""
        VK-like execute method for batch API requests (～￣▽￣)～
        
        Доступные методы и их назначение:
        - `user.list`: Получение списка всех пользователей (пагинировано). Зачем: для админки или списков.
        - `user.retrieve`: Получить инфу об одном пользователе (параметр `pk`). Зачем: профиль пользователя.
        - `marketplace.list`: Список всех приложений в магазине. Зачем: главная страница или лента.
        - `marketplace.retrieve`: Детали одного приложения (параметр `pk`). Зачем: страница приложения.
        - `marketplace.search`: Поиск приложений (параметр `query`). Зачем: строка поиска.
        - `category.list`: Список всех категорий. Зачем: боковое меню или фильтры.
        - `category.retrieve`: Детали категории (параметр `pk`). Зачем: заголовок страницы категории.
        - `category.apps`: Приложения внутри конкретной категории (параметр `pk`). Зачем: просмотр раздела (например, 'Игры').
        - `distribution.list`: Список всех сборок/дистрибутивов вообще. Зачем: техническая статистика.
        - `distribution.retrieve`: Детали одной сборки (параметр `pk`). Зачем: перед скачиванием.
        - `distribution.by_app`: Сборки конкретного приложения (параметр `app_id`). Зачем: вкладка 'Версии' на странице приложения.
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
                "marketplace.list": (MarketplaceViewSet, "list"),
                "marketplace.retrieve": (MarketplaceViewSet, "retrieve"),
                "marketplace.search": (MarketplaceViewSet, "search"),
                "category.list": (CategoryViewSet, "list"),
                "category.retrieve": (CategoryViewSet, "retrieve"),
                "category.apps": (CategoryViewSet, "apps"),
                "distribution.list": (DistributionViewSet, "list"),
                "distribution.retrieve": (DistributionViewSet, "retrieve"),
                "distribution.by_app": (DistributionViewSet, "by_app"),
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
