import pyotp
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.api.constants import ErrorCodes
from apps.api.exceptions import LunaException


from rest_framework import serializers

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

        # Manually generate tokens to inject refresh_jti into access token
        refresh = self.get_token(self.user)
        access = refresh.access_token
        access['refresh_jti'] = refresh['jti']
        
        data['refresh'] = str(refresh)
        data['access'] = str(access)

        return data
