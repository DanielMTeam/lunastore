from urllib.parse import urljoin

from django.conf import settings


def absolute_media_url(value):
    if not value:
        return None
    return urljoin(settings.API_MEDIA_BASE_URL, value)
