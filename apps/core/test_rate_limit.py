from types import SimpleNamespace
from unittest import mock

from django.core.cache.backends.locmem import LocMemCache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.core.middleware import RateLimitMiddleware


class RateLimitMiddlewareTests(SimpleTestCase):
    def test_configured_request_count_and_window(self):
        cache = LocMemCache("rate-limit-test", {})
        cache.clear()
        middleware = RateLimitMiddleware(lambda request: HttpResponse("OK"))
        factory = RequestFactory()
        config = SimpleNamespace(RATE_LIMIT_WINDOW=400, RATE_LIMIT=35)

        with mock.patch("apps.core.middleware.config", config), mock.patch(
            "apps.user.services.login_security.cache", cache
        ), mock.patch("django.core.cache.backends.locmem.time.time", return_value=1000) as clock:
            request = factory.get("/app.php", REMOTE_ADDR="192.0.2.1")
            for _ in range(400):
                response = middleware(request)
                self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-RateLimit-Limit"], "400")
            self.assertEqual(response["X-RateLimit-Remaining"], "0")
            self.assertEqual(middleware(request).status_code, 429)
            self.assertEqual(middleware(factory.get("/app.php", REMOTE_ADDR="192.0.2.2")).status_code, 200)

            clock.return_value = 1036
            self.assertEqual(middleware(request).status_code, 200)
