import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import requests


class CDNTokenValidationMixin:
    def validate_cdn_token(self, token, expected_type="cdn-confirm"):
        if not token:
            raise ValidationError(_("ERROR_CDN_TOKEN_MISSING"))

        try:
            # decode and validate token
            decoded = jwt.decode(
                token,
                settings.LUNASPIRE_SECRET_KEY,
                algorithms=["HS256"])

            if decoded.get("type") != expected_type:
                raise ValidationError(_("ERROR_CDN_TOKEN_INVALID_TYPE"))

            # check guard via cache (protection against reuse)
            token_guard = decoded.get("guard")
            if hasattr(self, 'user') and self.user and token_guard:
                cache_key = f"cdn_guard_{self.user.id}_{token_guard}"
                if not cache.get(cache_key):
                    raise ValidationError(_("ERROR_CDN_TOKEN_EXPIRED_OR_USED"))

                # delete from cache
                cache.delete(cache_key)

            return decoded

        except jwt.ExpiredSignatureError:
            raise ValidationError(_("ERROR_CDN_TOKEN_EXPIRED"))
        except jwt.InvalidTokenError:
            raise ValidationError(_("ERROR_CDN_TOKEN_INVALID"))

    def get_cdn_file_info(self, file_id, fields="hash"):
        """
        universal S2S request to CDN
        you can pass fields="hash" (for .exe) or fields="path" (for images)
        """
        payload = {
            "type": "cdn-info",
            "search_field": "id",
            "search_values": [str(file_id)],
            "send": fields  # <-- dynamic parameter
        }
        token = jwt.encode(
            payload,
            settings.LUNASPIRE_SECRET_KEY,
            algorithm="HS256")
        from apps.core.local import get_geo_spire_url
        spire_url = get_geo_spire_url(settings.LUNASPIRE_URL).rstrip('/')
        url = f"{spire_url}/cdn/info"

        try:
            response = requests.get(url, params={"token": token}, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 200 and data.get("info"):
                    # return all!!!00!!
                    return data["info"][0]
                else:
                    raise ValidationError(
                        f"Error in JSON-answer of LunaSpire: {data}")
            else:
                raise ValidationError(
                    f"CDN returned HTTP {
                        response.status_code}: {
                        response.text}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(
                f"CDN connect problem on: {url}. Error: {
                    str(e)}")
