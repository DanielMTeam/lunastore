from apps.user.services.login_security import increment_window
from constance import config
from django.http import JsonResponse
from django.conf import settings
import json
import logging
from apps.core.utils import get_client_ip

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(('/staticfiles/', '/media/')) or request.path.endswith('/heartbeat/'):
            return self.get_response(request)

        if request.path.lower().endswith(
            ('.png',
             '.jpg',
             '.jpeg',
             '.gif',
             '.css',
             '.js',
             '.woff',
             '.woff2',
             '.ico',
             '.svg',
             '.map',
             '.ttf',
             '.eot')):
            return self.get_response(request)

        # read rate limit values from constance at request time (live updates)
        rate_limit = int(config.RATE_LIMIT)
        time_window = int(config.RATE_LIMIT_WINDOW)

        ip = get_client_ip(request)
        cache_key = f'ratelimit_{ip}'

        try:
            requests = increment_window(cache_key, time_window)
        except Exception:
            return JsonResponse({"error": "Rate limiter unavailable."}, status=503)
        if requests > rate_limit:
            return JsonResponse({"error": "Too many requests. Please try again later."}, status=429)

        response = self.get_response(request)

        # optionally: add rate limit headers to the response
        response['X-RateLimit-Limit'] = rate_limit
        response['X-RateLimit-Remaining'] = max(0, rate_limit - requests)

        return response


class FallbackGeoRedirectMiddleware:
    # fallback redirects for standalone/self-host when reverse proxy is not doing them
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(config, 'GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS', False):
            if request.method in ('GET', 'HEAD') and not request.path.startswith(
                ('/media/', '/staticfiles/', '/static/', '/method/', '/v2/')
            ):
                from apps.core.utils import get_geo_domains
                geo_domains = get_geo_domains(request, allow_country_fallback=True)
                base_url = geo_domains.get('BASE_URL')
                if base_url:
                    current_host = request.get_host().split(':')[0].lower()
                    base_url_domain = base_url.split(':')[0].lower()
                    if current_host != base_url_domain:
                        from django.shortcuts import redirect
                        return redirect(f"{request.scheme}://{base_url}{request.get_full_path()}")

        return self.get_response(request)


# backward compatibility alias
GeoDomainMiddleware = FallbackGeoRedirectMiddleware
