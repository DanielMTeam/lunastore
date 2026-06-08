from constance import config
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import json
import logging
from apps.core.utils import get_client_ip, get_country_code

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(('/staticfiles/', '/media/')):
            return self.get_response(request)

        # read rate limit values from constance at request time (live updates)
        rate_limit = int(config.RATE_LIMIT)
        time_window = int(config.RATE_LIMIT_WINDOW)

        ip = get_client_ip(request)
        cache_key = f'ratelimit_{ip}'

        requests = cache.get(cache_key, 0)

        if requests >= rate_limit:
            # if we exceed the rate limit, return a 429 response
            return JsonResponse(
                {'error': 'Too many requests. Please try again later.'},
                status=429
            )

        # if this is the first request, set the cache key with TTL
        if requests == 0:
            cache.set(cache_key, 1, time_window)
        else:
            # increment the request count atomically
            try:
                cache.incr(cache_key)
            except ValueError:
                # On cache miss (key expired between get and incr), reset to 1
                cache.set(cache_key, 1, time_window)

        response = self.get_response(request)

        # optionally: add rate limit headers to the response
        response['X-RateLimit-Limit'] = rate_limit
        response['X-RateLimit-Remaining'] = max(0, rate_limit - (requests + 1))

        return response


class GeoDomainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        country_code = get_country_code(ip)

        # Default domains
        geo_domains = {
            "BASE_URL": settings.LUNASPIRE_URL_WITHOUT_PROTO,
            "API_URL": settings.API_URL,
            "SPIRE_URL": settings.LUNASPIRE_URL,
        }

        # Override domains if present in config and enabled
        if getattr(config, 'GEO_DOMAIN_PROXY_ENABLED', True):
            raw_overrides = getattr(config, 'GEO_DOMAIN_OVERRIDES', '{}')
            try:
                overrides = json.loads(raw_overrides)
                if country_code in overrides:
                    country_overrides = overrides[country_code]
                    if isinstance(country_overrides, dict):
                        # update with matched ones
                        if 'BASE_URL' in country_overrides:
                            geo_domains['BASE_URL'] = country_overrides['BASE_URL']
                        if 'API_URL' in country_overrides:
                            geo_domains['API_URL'] = country_overrides['API_URL']
                        if 'SPIRE_URL' in country_overrides:
                            geo_domains['SPIRE_URL'] = country_overrides['SPIRE_URL']
            except json.JSONDecodeError:
                logger.error("Failed to parse GEO_DOMAIN_OVERRIDES json in Constance config.")
            except Exception as e:
                logger.error(f"Error processing geo domains: {e}")

        request.geo_domains = geo_domains
        return self.get_response(request)
