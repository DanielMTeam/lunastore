import pyotp
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.api.constants import ErrorCodes
from apps.api.exceptions import LunaException


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['totp_code'] = self.fields.get('totp_code', None)

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

        # Custom lifetimes if provided
        from datetime import timedelta

        refresh_lifetime_days = self.initial_data.get('refresh_lifetime_days')
        access_lifetime_minutes = self.initial_data.get('access_lifetime_minutes')

        if refresh_lifetime_days is not None or access_lifetime_minutes is not None:
            # Generate new tokens to apply custom lifetimes
            refresh = self.get_token(self.user)

            if refresh_lifetime_days is not None:
                try:
                    days = int(refresh_lifetime_days)
                    if 1 <= days <= 365:
                        refresh.set_exp(lifetime=timedelta(days=days))
                except ValueError:
                    pass

            access = refresh.access_token
            if access_lifetime_minutes is not None:
                try:
                    minutes = int(access_lifetime_minutes)
                    if 1 <= minutes <= 1440:  # max 24 hours for access token
                        access.set_exp(lifetime=timedelta(minutes=minutes))
                except ValueError:
                    pass

            data['refresh'] = str(refresh)
            data['access'] = str(access)

        return data
