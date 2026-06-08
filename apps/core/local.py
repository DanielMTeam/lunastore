import threading

_thread_locals = threading.local()

def set_current_request(request):
    _thread_locals.request = request

def get_current_request():
    return getattr(_thread_locals, 'request', None)

def get_geo_spire_url(default):
    req = get_current_request()
    if req and hasattr(req, 'geo_domains'):
        return req.geo_domains.get('SPIRE_URL', default)
    return default
