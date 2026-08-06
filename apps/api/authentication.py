from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.core.cache import cache


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that checks if the access token's JTI is in the cache blacklist.
    """
    def get_validated_token(self, raw_token):
        validated_token = super().get_validated_token(raw_token)

        jti = validated_token.get('refresh_jti')
        if jti:
            # Check if this JTI is in the cache blacklist
            cache_key = f"token_blacklist_{jti}"
            if cache.get(cache_key):
                raise AuthenticationFailed(
                    "Token is blacklisted",
                    code="token_not_valid",
                )

        return validated_token
