import time
import uuid
from datetime import datetime
from django.utils import timezone

import jwt
from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.marketplace.models import Application, Category, Distribution
from apps.marketplace.serializers import (
    ApplicationSerializer,
    CategorySerializer,
    DistributionSerializer,
)
from apps.user.models import User
from apps.user.serializers import UserSerializer
from apps.core.notifications.services import NotificationService

from .constants import ErrorCodes
from .exceptions import LunaException
from django.core.cache import cache


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer

    PUB_UPLOAD_POLICIES = {
        "avatar": {
            "mw": 512,
            "mh": 512,
            "mimes": "image/jpeg;image/png;image/webp",
            "obj": "avatar",
        },
        "icon": {
            "mw": 512,
            "mh": 512,
            "mimes": "image/jpeg;image/png;image/webp",
            "obj": "icon",
        },
        "screenshot": {
            "mw": 1920,
            "mh": 1080,
            "mimes": "image/jpeg;image/png;image/webp",
            "obj": "screenshot",
        },
    }

    @extend_schema(
        summary="get user profile info",
        description="returns user info",
        parameters=[
            OpenApiParameter(
                name="id",
                description="User ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="getProfileInfo")
    def get_profile(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )

        try:
            user = self.get_queryset().get(pk=id)
        except User.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.USER_NOT_FOUND,
                message=f"User with id {id} was not found",
                status_code=404,
            )

        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="getPubUploadToken",
        permission_classes=[IsAuthenticated],
    )
    def get_pub_upload_token(self, request):
        target = request.query_params.get("target")

        if not target or target not in self.PUB_UPLOAD_POLICIES:
            return Response({"error": "Invalid target"}, status=400)

        policy = self.PUB_UPLOAD_POLICIES[target]
        guard_phrase = str(uuid.uuid4().hex)[:8]

        cache_key = f"cdn_guard_{request.user.id}_{guard_phrase}"
        cache.set(cache_key, True, timeout=180)

        current_time = int(time.time())

        payload = {
            "type": "cdn-upload",
            "object": policy["obj"],
            "user": str(request.user.id),
            "guard": guard_phrase,
            "mode": "public",
            "accept": policy["mimes"],
            "iat": current_time,
            "exp": current_time + 180,
            "img_opts": {"mw": policy["mw"], "mh": policy["mh"]},
        }

        upload_token = jwt.encode(
            payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"
        )
        return Response({"upload_token": upload_token, "guard": guard_phrase})

    @action(
        detail=False,
        methods=["get"],
        url_path="getPrivUploadToken",
        permission_classes=[IsAuthenticated],
    )
    def get_priv_upload_token(self, request):
        target = request.query_params.get(
            "target", "distribution"
        )  # for future updates
        app_id = request.query_params.get("app_id")

        if not app_id:
            return Response({"error": "app_id is required"}, status=400)

        if not app_id.isdigit():
            return Response({"error": "app_id must be a valid integer"}, status=400)

        # check permissions
        app_obj = get_object_or_404(Application, id=app_id)
        if app_obj.user != request.user:
            return Response({"error": "Not your app"}, status=403)

        guard_phrase = str(uuid.uuid4().hex)[:8]

        cache_key = f"cdn_guard_{request.user.id}_{guard_phrase}"
        cache.set(cache_key, True, timeout=180)

        current_time = int(time.time())

        allowed_mimes = ";".join(
            [
                # universal binary stream (fallback)
                "application/octet-stream",

                # .exe (Windows Executables)
                "application/x-msdownload",
                "application/exe",
                "application/x-exe",
                "application/dos-exe",
                "application/x-winexe",
                "application/msdos-windows",
                "application/x-msdos-program",

                # .msi (Windows Installer)
                "application/x-msi",
                "application/x-ms-installer",
                "application/x-windows-installer",
                "application/x-ole-storage",

                # .zip (ZIP Archives)
                "application/zip",
                "application/x-zip-compressed",
                "application/x-zip",
                "multipart/x-zip",

                # .rar (RAR Archives)
                "application/vnd.rar",
                "application/x-rar-compressed",
                "application/x-rar",
                "application/rar",

                # .7z (7-Zip Archives)
                "application/x-7z-compressed",
                "application/7z",
            ]
        )

        payload = {
            "type": "cdn-upload",
            "object": str(app_obj.id),  # object this is a id of the app
            "user": str(request.user.id),
            "guard": guard_phrase,
            "mode": "private",  # private only
            "accept": allowed_mimes,
            "iat": current_time,
            "exp": current_time + 180,
        }

        upload_token = jwt.encode(
            payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"
        )
        return Response({"upload_token": upload_token, "guard": guard_phrase})

    @action(detail=False, methods=["get"], url_path="getNotificationToken", permission_classes=[IsAuthenticated])
    def get_notification_token(self, request):
        token = NotificationService.get_receive_token(request.user.id)
        return Response({"token": token, "ws_url": settings.LUNASPIRE_URL})

class MarketplaceViewSet(viewsets.GenericViewSet):
    queryset = Application.objects.filter()
    serializer_class = ApplicationSerializer

    @extend_schema(
        summary="get app info",
        description="returns app info",
        parameters=[
            OpenApiParameter(
                name="id",
                description="Application ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="getAppInfo")
    def get_app(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )
        try:
            app = self.get_queryset().get(pk=id)
        except Application.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"Application with id {id} was not found",
                status_code=404,
            )
        if app.is_under_dmca:
            raise LunaException(
                code=ErrorCodes.APPLICATION_IS_UNDER_DMCA,
                message=f"Application (id: {id}) unavailable because his creators/uploaders received a DMCA strike",
                status_code=403,
            )
        if app.is_private:
            raise LunaException(
                code=ErrorCodes.APPLICATION_PRIVATE,
                message=f"Application (id: {id}) unavailable because it is private",
                status_code=403,
            )
        serializer = self.get_serializer(app)
        return Response(serializer.data)

    @extend_schema(
        summary="get app or apps from name (e.g. search app method)",
        description="returns app, or list of apps",
        parameters=[
            OpenApiParameter(
                name="query",
                description="query data",
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: ApplicationSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        query = request.query_params.get("query")

        if not query:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'query' field missing",
                status_code=400,
            )
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

        serializer = ApplicationSerializer(results, many=True)
        enumerated_data = {
            str(index + 1): results for index, results in enumerate(serializer.data)
        }
        return Response(enumerated_data)


class CategoryViewSet(viewsets.GenericViewSet):
    queryset = Category.objects.filter()
    serializer_class = CategorySerializer

    @extend_schema(
        summary="get app list from category",
        description="returns app list from category",
        parameters=[
            OpenApiParameter(
                name="id",
                description="Category ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: ApplicationSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="getAppList")
    def get_app_list(self, request):
        id = request.query_params.get("id")

        if not id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )
        try:
            category = self.get_queryset().get(pk=id)
            apps = Application.objects.filter(category=category).exclude(is_private=True).order_by("-published")
        except Category.DoesNotExist:
            raise LunaException(
                code=ErrorCodes.CATEGORY_NOT_FOUND,
                message=f"Category with id {id} was not found",
                status_code=404,
            )

        serializer = ApplicationSerializer(apps, many=True)
        enumerated_data = {
            str(index + 1): apps for index, apps in enumerate(serializer.data)
        }
        return Response(enumerated_data)


class ServiceViewSet(viewsets.GenericViewSet):
    @extend_schema(
        summary="check API status",
        description="API method like 'heartbeat' type; returns current time, status and version",
        responses={
            200: inline_serializer(
                name="HeartbeatResponse",
                fields={
                    "status": serializers.CharField(),
                    "timestamp": serializers.DateTimeField(),
                    "version": serializers.CharField(),
                },
            )
        },
    )
    @action(detail=False, methods=["get"], url_path="heartbeat")
    def heartbeat(self, request):
        return Response(
            {"status": "ok", "timestamp": timezone.now(), "version": settings.VERSION}
        )

    @extend_schema(
        summary="returns list of LunaStore developers",
        description="returns list of LunaStore developers",
    )
    @action(detail=False, methods=["get"], url_path="developersList")
    def developers(self, request):
        return Response(
            {
                "creator": "Daniel Myslivets",
                "backend": "fayzetwin, synzr, filldor, zazios",
                "frontend": "Daniel Myslivets",
                "system-administration": "eversiege, thefoxmilya, rotama",
                "design": "chelka0",
                "special_thanks": "MondySpartan (logo), nocha3 (native client of LunaStore for Windows XP)",
            }
        )

    @extend_schema(
        summary="returns one cool thing",
        description="returns one cool thing",
    )
    @action(detail=False, methods=["get"], url_path="kunyakin")
    def kunyakin(self, request):
        return Response({"answer": "влад кунякин пробудил шаринган"})


class DistributionViewSet(viewsets.GenericViewSet):
    queryset = Distribution.objects.filter()
    serializer_class = DistributionSerializer

    @extend_schema(
        summary="get list of distributions from app",
        description="returns list of distributions from app",
        parameters=[
            OpenApiParameter(
                name="id",
                description="Application ID",
                required=True,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={200: DistributionSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="getDistributionsList")
    def get_distributions_list(self, request):
        app_id = request.query_params.get("id")

        if not app_id:
            raise LunaException(
                code=ErrorCodes.VALIDATION_ERROR,
                message="'ID' field missing",
                status_code=400,
            )

        if not Application.objects.filter(id=app_id).exists():
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"Application with id {app_id} was not found",
                status_code=404,
            )

        # get distributions
        distributions = self.get_queryset().filter(app_id=app_id)

        if not distributions.exists():
            raise LunaException(
                code=ErrorCodes.APPLICATION_NOT_FOUND,
                message=f"No distributions found for app id {app_id}",
                status_code=404,
            )

        serializer = DistributionSerializer(distributions, many=True)

        enumerated_data = {
            str(index + 1): dist_data
            for index, dist_data in enumerate(serializer.data)
        }

        return Response(enumerated_data)
