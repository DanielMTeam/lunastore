from constance import config
from django.core.cache import cache
from django.http import JsonResponse
from apps.core.utils import get_client_ip


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

