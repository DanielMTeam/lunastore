from urllib.parse import urljoin, urlsplit

from django.conf import settings


def absolute_media_url(value):
    if not value:
        return None
    return urljoin(settings.API_MEDIA_BASE_URL, value)


def public_api_url(value):
    if value is None or settings.API_PUBLIC_SCHEME not in ("http", "https"):
        return value
    return urlsplit(value)._replace(scheme=settings.API_PUBLIC_SCHEME).geturl()
