import pyotp
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.api.constants import ErrorCodes
from apps.api.exceptions import LunaException
from constance import config
import logging


from rest_framework import serializers
from apps.core.utils import get_client_ip
from apps.user.services.antispam import AntiSpamService, NoSpamContext

logger = logging.getLogger("user")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    totp_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        # We need to extract totp_code manually as it's not a standard field
        totp_code = self.initial_data.get('totp_code')

        # Standard validation (checks username and password)
        data = super().validate(attrs)

        # If credentials are correct, self.user is populated
        if self.user and self.user.totp_secret:
            if not totp_code:
                raise LunaException(
                    code=ErrorCodes.TWO_FACTOR_REQUIRED,
                    message="Two-factor authentication is enabled. Please provide 'totp_code'.",
                    status_code=401
                )

            totp = pyotp.TOTP(self.user.totp_secret)
            if not totp.verify(totp_code):
                raise LunaException(
                    code=ErrorCodes.TWO_FACTOR_INVALID,
                    message="Invalid two-factor authentication code.",
                    status_code=401
                )

        request = self.context.get("request")
        if request is not None and self.user is not None:
            context = NoSpamContext(
                entrypoint="jwt_token",
                ip=get_client_ip(request),
                email=self.user.email,
                username=self.user.username,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                user=self.user,
                extra={"path": request.path},
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

        # Manually generate tokens to inject refresh_jti into access token
        refresh = self.get_token(self.user)
        access = refresh.access_token
        access['refresh_jti'] = refresh['jti']

        data['refresh'] = str(refresh)
        data['access'] = str(access)

        return data
