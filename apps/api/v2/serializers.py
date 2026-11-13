from rest_framework_simplejwt.serializers import TokenObtainSerializer, TokenRefreshSerializer
from apps.api.token_sessions import issue_tokens, rotate_tokens, validate_account
from apps.user.services.bans import is_ip_banned
from apps.user.services.login_security import allow_password_attempt, allow_totp_attempt, verify_totp
from apps.api.constants import ErrorCodes
from apps.api.exceptions import LunaException
from constance import config
import logging


from rest_framework import serializers
from apps.core.utils import get_client_ip, get_country_from_request
from apps.user.services.antispam import AntiSpamService, NoSpamContext

logger = logging.getLogger("user")


class CustomTokenObtainPairSerializer(TokenObtainSerializer):
    totp_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        if request and is_ip_banned(get_client_ip(request)):
            raise LunaException(code=ErrorCodes.USER_IS_BLOCKED, message="Authentication unavailable.", status_code=403)
        if not allow_password_attempt(request, attrs[self.username_field]):
            raise LunaException(code=ErrorCodes.VALIDATION_ERROR, message="Too many attempts.", status_code=429)
        super().validate(attrs)
        validate_account(self.user)
        totp_code = attrs.get("totp_code")
        if self.user.totp_enabled:
            if not totp_code:
                raise LunaException(
                    code=ErrorCodes.TWO_FACTOR_REQUIRED,
                    message="Two-factor authentication is enabled. Please provide 'totp_code'.",
                    status_code=401
                )

            if not allow_totp_attempt(self.user) or not verify_totp(self.user, totp_code):
                raise LunaException(
                    code=ErrorCodes.TWO_FACTOR_INVALID,
                    message="Invalid two-factor authentication code.",
                    status_code=401
                )

        if request is not None and self.user is not None:
            context = NoSpamContext(
                entrypoint="jwt_token",
                ip=get_client_ip(request),
                email=self.user.email,
                username=self.user.username,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                user=self.user,
                extra={"path": request.path, "country_code": get_country_from_request(request)},
            )
            try:
                decision = AntiSpamService.evaluate_and_apply(
                    context=context, target_user=self.user)
            except Exception as exc:
                logger.exception("nospam jwt guard failed: %s", exc)
                fail_mode = str(getattr(config, "NOSPAM_FAIL_MODE", "allow")).lower()
                if fail_mode == "deny":
                    raise LunaException(
                        code=ErrorCodes.UNKNOWN_ERROR,
                        message="Authentication temporarily unavailable.",
                        status_code=503,
                    )
                decision = None

            if decision and decision.should_block:
                raise LunaException(
                    code=ErrorCodes.USER_IS_BLOCKED,
                    message="Authentication unavailable for this account.",
                    status_code=403,
                )

        return issue_tokens(self.user)


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        request = self.context.get("request")
        if request and is_ip_banned(get_client_ip(request)):
            raise LunaException(code=ErrorCodes.USER_IS_BLOCKED, message="Authentication unavailable.", status_code=403)
        return rotate_tokens(attrs["refresh"])
