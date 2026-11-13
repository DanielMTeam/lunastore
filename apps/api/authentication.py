from rest_framework_simplejwt.authentication import JWTAuthentication

from rest_framework_simplejwt.exceptions import InvalidToken

from apps.core.utils import get_client_ip
from apps.user.services.bans import is_ip_banned

from .token_sessions import get_api_session, validate_account


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None and is_ip_banned(get_client_ip(request)):
            raise InvalidToken("Authentication unavailable for this address.")
        return result

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        get_api_session(validated_token)
        validate_account(user, validated_token)
        return user
