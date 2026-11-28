import threading

_thread_locals = threading.local()


def set_current_request(request):
    _thread_locals.request = request


def get_current_request():
    return getattr(_thread_locals, 'request', None)


def get_geo_spire_url(default):
    req = get_current_request()
    if req:
        from apps.core.utils import get_geo_domains
        return get_geo_domains(req).get('SPIRE_URL', default)
    return default


def spire_media_url(path):
    from django.conf import settings

    origin = get_geo_spire_url(settings.LUNASPIRE_URL).strip().rstrip("/")
    host_and_path = origin.removeprefix("https://").removeprefix("http://").lstrip("/")
    return f"//{host_and_path}/{path.lstrip('/')}"
