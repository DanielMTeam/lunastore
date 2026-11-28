from datetime import UTC, datetime

from django.utils.cache import add_never_cache_headers
from drf_spectacular.utils import extend_schema, extend_schema_serializer
from rest_framework import exceptions, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.api.authentication import CustomJWTAuthentication
from apps.api.media import public_api_url
from apps.api.token_sessions import revoke_tokens
from apps.api.v2.serializers import CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer, TokenPairSerializer
from apps.core.notifications.services import NotificationService, NotificationsThrottled, NotificationsUnavailable

from .catalog import validated_query
from .contract import V3ContractMixin
from .serializers import UserSerializer


class PrivateResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        add_never_cache_headers(response)
        return response


class AccountView(PrivateResponseMixin, V3ContractMixin, APIView):
    authentication_classes = (CustomJWTAuthentication,)
    permission_classes = (IsAuthenticated,)


@extend_schema_serializer(component_name="V3Me")
class MeSerializer(UserSerializer):
    is_developer = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "description", "avatar_url", "is_developer")

    def get_is_developer(self, user) -> bool:
        return user.groups.filter(name="Разработчики").exists()


class MeView(AccountView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class NotificationParams(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, max_value=2147483647, default=1)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)


class NotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    content = serializers.CharField()
    type = serializers.CharField()
    created_at = serializers.DateTimeField(default_timezone=UTC)
    read_at = serializers.DateTimeField(allow_null=True, default_timezone=UTC)


class NotificationPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = NotificationSerializer(many=True)
    unread_count = serializers.IntegerField()


class NotificationServiceUnavailable(exceptions.APIException):
    status_code = 503
    default_detail = "Notifications are temporarily unavailable."
    default_code = "notifications_unavailable"


def notification_error(exc):
    if isinstance(exc, NotificationsThrottled):
        return exceptions.Throttled(wait=exc.retry_after)
    return NotificationServiceUnavailable()


class NotificationsView(AccountView):
    @extend_schema(parameters=[NotificationParams], responses=NotificationPageSerializer)
    def get(self, request):
        params = validated_query(NotificationParams, request)
        page, limit = params["page"], params["limit"]
        try:
            data = NotificationService.list_notifications(request.user.pk, page=page, limit=limit)
        except NotificationsUnavailable as exc:
            raise notification_error(exc) from exc
        try:
            total = data["total"]
            unread = data["total_unread"]
            if type(total) is not int or type(unread) is not int or not 0 <= unread <= total:
                raise ValueError("Invalid notification counts")
            results = [
                {
                    "id": item["ID"],
                    "title": item["Title"],
                    "content": item["Content"],
                    "type": (item.get("Meta") or {}).get("type", "normal"),
                    "created_at": datetime.fromtimestamp(item["CreatedAt"], UTC),
                    "read_at": datetime.fromtimestamp(item["ViewedAt"], UTC) if item.get("ViewedAt") else None,
                }
                for item in (data["data"] if data["data"] is not None else [])
            ]
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise NotificationServiceUnavailable() from exc

        def link(number):
            return public_api_url(request.build_absolute_uri(f"?page={number}&limit={limit}"))

        return Response(NotificationPageSerializer({
            "count": total,
            "next": link(page + 1) if page * limit < total else None,
            "previous": link(page - 1) if page > 1 else None,
            "results": results,
            "unread_count": unread,
        }).data)


class MarkNotificationsReadView(AccountView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        try:
            NotificationService.mark_all_read(request.user.pk)
        except NotificationsUnavailable as exc:
            raise notification_error(exc) from exc
        return Response(status=204)


class TokenObtainView(PrivateResponseMixin, V3ContractMixin, TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(responses=TokenPairSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TokenRotateView(PrivateResponseMixin, V3ContractMixin, TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer

    @extend_schema(responses=TokenPairSerializer)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RevokeSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False, write_only=True)


class TokenRevokeView(PrivateResponseMixin, V3ContractMixin, APIView):
    authentication_classes = ()

    @extend_schema(request=RevokeSerializer, responses={204: None})
    def post(self, request):
        serializer = RevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            revoke_tokens(serializer.validated_data["refresh"])
        except TokenError as exc:
            raise InvalidToken("Invalid refresh token.") from exc
        return Response(status=204)

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'
