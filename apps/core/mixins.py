import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import requests


class CDNTokenValidationMixin:
    def validate_cdn_token(self, token, expected_type="cdn-confirm", expected_object=None, expected_mode=None):
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
            if expected_object is not None and not (getattr(self, 'user', None) and token_guard):
                raise ValidationError(_("ERROR_CDN_TOKEN_INVALID"))
            if hasattr(self, 'user') and self.user and token_guard:
                cache_key = f"cdn_guard_{self.user.id}_{token_guard}"
                upload_context = cache.get(cache_key)
                if not upload_context:
                    raise ValidationError(_("ERROR_CDN_TOKEN_EXPIRED_OR_USED"))

                if expected_object is not None and (
                    not isinstance(upload_context, dict)
                    or upload_context.get("object") != str(expected_object)
                    or upload_context.get("mode") != expected_mode
                ):
                    raise ValidationError(_("ERROR_CDN_TOKEN_INVALID"))

                if not cache.add(f"{cache_key}_used", True, timeout=3600):
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
        # Browsers support protocol-relative URLs; server requests require a scheme.
        if spire_url.startswith('//'):
            spire_url = 'https:' + spire_url
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
