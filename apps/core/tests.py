import json
import logging
import os
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.checks import Tags, run_checks
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.marketplace.models import (
    Application,
    Category,
    Collection,
    CollectionItem,
    Distribution,
)

logger = logging.getLogger("core")
User = get_user_model()


class SitemapAndRobotsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info("[Core APP; Sitemap TEST] Setting up test data...")
        cls.author = User.objects.create_user(
            username="author_user",
            password="testpassword123",
            email="author@example.com",
            is_active=True,
        )
        cls.inactive_user = User.objects.create_user(
            username="inactive_user",
            password="testpassword123",
            email="inactive@example.com",
            is_active=False,
        )

        cls.public_category = Category.objects.create(
            name="PublicCategory",
            description="Public category description",
            is_admin_only=False,
        )
        cls.admin_category = Category.objects.create(
            name="AdminCategory",
            description="Admin category description",
            is_admin_only=True,
        )

        cls.public_app = Application.objects.create(
            user=cls.author,
            title="PublicApp",
            description="Public app description",
            is_private=False,
            is_under_dmca=False,
        )
        cls.public_app.categories.add(cls.public_category)

        cls.dmca_app = Application.objects.create(
            user=cls.author,
            title="DmcaApp",
            description="Dmca app description",
            is_private=False,
            is_under_dmca=True,
        )

        cls.distribution = Distribution.objects.create(
            app=cls.public_app,
            version="1.0.0",
            url="https://example.com/dist.zip",
            changelog="Initial release",
        )

        cls.dmca_distribution = Distribution.objects.create(
            app=cls.dmca_app,
            version="1.0.0",
            url="https://example.com/dmca.zip",
            changelog="DMCA release",
        )

        cls.private_app = Application.objects.create(
            user=cls.author,
            title="PrivateApp",
            description="Private app description",
            is_private=True,
        )

        cls.deleted_app = Application.objects.create(
            user=cls.author,
            title="DeletedApp",
            description="Deleted app description",
            is_private=False,
        )
        cls.deleted_app.delete()

        cls.public_collection = Collection.objects.create(
            owner=cls.author,
            title="PublicCollection",
            description="Public collection description",
            is_public=True,
            is_system=False,
        )
        CollectionItem.objects.create(
            collection=cls.public_collection,
            application=cls.public_app,
        )

        cls.empty_collection = Collection.objects.create(
            owner=cls.author,
            title="EmptyCollection",
            description="Empty collection",
            is_public=True,
            is_system=False,
        )

        cls.private_collection = Collection.objects.create(
            owner=cls.author,
            title="PrivateCollection",
            description="Private collection description",
            is_public=False,
            is_system=False,
        )
        cls.system_collection = Collection.objects.create(
            owner=cls.author,
            title="Likes",
            description="System likes",
            is_public=True,
            is_system=True,
        )

    def test_sitemap_xml_response(self):
        logger.info("[Core APP; Sitemap TEST] Testing /sitemap.xml...")
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.headers["Content-Type"])

        content = response.content.decode("utf-8")
        # Check public items
        self.assertIn("/index.php", content)
        self.assertIn(f"/category.php?id={self.public_category.id}", content)
        self.assertIn(f"/app.php?id={self.public_app.id}", content)
        self.assertIn(f"/download.php?id={self.public_app.id}", content)
        self.assertIn(f"/collections.php?page=view&amp;id={self.public_collection.id}", content)
        self.assertIn(f"/profile.php?id={self.author.id}", content)
        self.assertIn("/help_center.php?page=faq", content)

        # Check that private/admin/dmca/empty items are excluded
        self.assertNotIn(f"/app.php?id={self.dmca_app.id}", content)
        self.assertNotIn(f"/download.php?id={self.dmca_app.id}", content)
        self.assertNotIn(f"/category.php?id={self.admin_category.id}", content)
        self.assertNotIn(f"/app.php?id={self.private_app.id}", content)
        self.assertNotIn(f"/app.php?id={self.deleted_app.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.empty_collection.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.private_collection.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.system_collection.id}", content)
        self.assertNotIn(f"/profile.php?id={self.inactive_user.id}", content)
        self.assertNotIn("/admin/", content)
        self.assertNotIn("/login.php", content)

    def test_sitemap_sections(self):
        logger.info("[Core APP; Sitemap TEST] Testing /sitemap-<section>.xml...")
        for section in ["static", "categories", "apps", "downloads", "collections", "authors"]:
            response = self.client.get(f"/sitemap-{section}.xml")
            self.assertEqual(response.status_code, 200)
            self.assertIn("application/xml", response.headers["Content-Type"])

    def test_robots_txt_response(self):
        logger.info("[Core APP; Sitemap TEST] Testing /robots.txt...")
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["Content-Type"])
        self.assertEqual(response.headers.get("Cache-Control"), "public, max-age=86400")

        content = response.content.decode("utf-8")
        self.assertIn("User-agent: *", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /method/", content)
        self.assertIn("Disallow: /login.php", content)
        self.assertIn("Disallow: /register.php", content)
        self.assertIn("Disallow: /settings.php", content)
        self.assertIn("Disallow: /app_add.php", content)
        self.assertIn("Sitemap: https://testserver/sitemap.xml", content)


class TLSVerificationChecksTest(TestCase):
    def _security_issue_ids(self):
        return [issue.id for issue in run_checks(tags=[Tags.security])]

    def test_oidc_insecure_warning(self):
        with override_settings(OIDC_VERIFY_SSL=False):
            self.assertIn("core.W001", self._security_issue_ids())

    def test_oidc_missing_bundle_warning(self):
        with override_settings(OIDC_VERIFY_SSL="certs/definitely-missing.pem"):
            self.assertIn("core.W002", self._security_issue_ids())

    @mock.patch.dict(os.environ, {"LUNAPASSPORT_VERIFY_SSL": "False"})
    def test_lunapassport_insecure_warning(self):
        self.assertIn("core.W004", self._security_issue_ids())

    def test_sentry_missing_bundle_warning(self):
        with override_settings(SENTRY_CA_BUNDLE="certs/definitely-missing.pem"):
            self.assertIn("core.W005", self._security_issue_ids())

    def test_lunapassport_invalid_bundle_warning(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as fh:
            fh.write(b"not a pem certificate")
            bundle_path = fh.name
        try:
            with mock.patch.dict(os.environ, {"LUNAPASSPORT_CA_BUNDLE": bundle_path}):
                self.assertIn("core.W003", self._security_issue_ids())
        finally:
            os.unlink(bundle_path)


class TasksAndWorkerIntegrationTest(TestCase):
    def test_send_telegram_notification_missing_config(self):
        from apps.core.tasks import send_telegram_notification_task

        with override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_LOG_CHAT_ID=""):
            result = send_telegram_notification_task.call("test message")
            self.assertFalse(result)

    @mock.patch("apps.core.tasks.requests.post")
    def test_send_telegram_notification_success(self, mock_post):
        from apps.core.tasks import send_telegram_notification_task

        mock_post.return_value.status_code = 200

        with override_settings(
            TELEGRAM_BOT_TOKEN="mock_token",
            TELEGRAM_LOG_CHAT_ID="12345",
            TELEGRAM_LOG_TOPIC_ID=678,
        ):
            result = send_telegram_notification_task.call("hello telegram")
            self.assertTrue(result)
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            self.assertEqual(call_kwargs["json"]["chat_id"], "12345")
            self.assertEqual(call_kwargs["json"]["text"], "hello telegram")
            self.assertEqual(call_kwargs["json"]["message_thread_id"], 678)

    @mock.patch("apps.core.tasks.time.sleep")
    @mock.patch("apps.core.tasks.requests.post")
    def test_send_telegram_notification_rate_limit_retry(self, mock_post, mock_sleep):
        from apps.core.tasks import send_telegram_notification_task

        resp_429 = mock.MagicMock()
        resp_429.status_code = 429
        resp_429.json.return_value = {"parameters": {"retry_after": 2}}

        resp_200 = mock.MagicMock()
        resp_200.status_code = 200

        mock_post.side_effect = [resp_429, resp_200]

        with override_settings(
            TELEGRAM_BOT_TOKEN="mock_token",
            TELEGRAM_LOG_CHAT_ID="12345",
        ):
            result = send_telegram_notification_task.call("retry test", max_retries=2)
            self.assertTrue(result)
            self.assertEqual(mock_post.call_count, 2)
            mock_sleep.assert_called_with(2)

    @mock.patch("apps.core.tasks.time.sleep")
    @mock.patch("apps.core.tasks.requests.post")
    def test_send_telegram_notification_retry_on_network_failure(self, mock_post, mock_sleep):
        import requests
        from apps.core.tasks import send_telegram_notification_task

        mock_post.side_effect = requests.RequestException("Connection timed out")

        with override_settings(
            TELEGRAM_BOT_TOKEN="mock_token",
            TELEGRAM_LOG_CHAT_ID="12345",
        ):
            result = send_telegram_notification_task.call("fail test", max_retries=3, retry_delay=0.1)
            self.assertFalse(result)
            self.assertEqual(mock_post.call_count, 3)

    def test_send_telegram_notification_helper_enqueues(self):
        from apps.core.tasks import send_telegram_notification

        with mock.patch("apps.core.tasks.send_telegram_notification_task") as mock_task:
            with self.captureOnCommitCallbacks(execute=True):
                send_telegram_notification("queue test message")
            mock_task.enqueue.assert_called_once_with("queue test message")

    @mock.patch("apps.core.tasks.NotificationService.send_notification")
    def test_broadcast_notification_task(self, mock_send_notif):
        from apps.core.tasks import broadcast_notification_task

        mock_send_notif.return_value = True

        delivered = broadcast_notification_task.call(
            user_ids=[101, 102, 103],
            title="Broadcast Title",
            content="Broadcast Body",
        )
        self.assertEqual(delivered, 3)
        self.assertEqual(mock_send_notif.call_count, 3)

    def test_run_tasks_worker_command_execution(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("run_tasks_worker", max_tasks=1, stdout=out)
        output = out.getvalue()
        self.assertIn("Starting LunaStore Redis task worker", output)


@override_settings(ROOT_URLCONF="lunastore.urls_private", MEILISEARCH_ENABLED=False)
class AdminBroadcastNotificationViewTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin_broadcast_test",
            password="adminpassword123",
            email="admin_broadcast@example.com",
        )
        self.user1 = User.objects.create_user(
            username="user1_broadcast_test",
            password="password123",
            email="user1_broadcast@example.com",
            is_active=True,
        )
        self.user2 = User.objects.create_user(
            username="user2_broadcast_test",
            password="password123",
            email="user2_broadcast@example.com",
            is_active=True,
        )
        self.inactive_user = User.objects.create_user(
            username="inactive_broadcast_test",
            password="password123",
            email="inactive_broadcast@example.com",
            is_active=False,
        )
        self.client.force_login(self.superuser)

    @mock.patch("apps.core.admin_views.broadcast_notification_task")
    def test_broadcast_to_single_user(self, mock_task):
        url = reverse("broadcast")
        response = self.client.post(url, {
            "title": "Important Notification",
            "content": "Message for single user",
            "level": "important",
            "user_id": self.user1.id,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        mock_task.enqueue.assert_called_once_with(
            user_ids=[self.user1.id],
            title="Important Notification",
            content="Message for single user",
            meta={"type": "important", "icon": "system.png"},
        )
        messages_list = list(response.context["messages"])
        self.assertTrue(any(f"ID {self.user1.id}" in str(m) for m in messages_list))

    @mock.patch("apps.core.admin_views.broadcast_notification_task")
    def test_broadcast_to_all_active_users(self, mock_task):
        url = reverse("broadcast")
        response = self.client.post(url, {
            "title": "Broadcast Notification",
            "content": "Message for all active users",
            "level": "normal",
            "user_id": "",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        mock_task.enqueue.assert_called_once()
        called_kwargs = mock_task.enqueue.call_args.kwargs
        self.assertIn(self.user1.id, called_kwargs["user_ids"])
        self.assertIn(self.user2.id, called_kwargs["user_ids"])
        self.assertIn(self.superuser.id, called_kwargs["user_ids"])
        self.assertNotIn(self.inactive_user.id, called_kwargs["user_ids"])
        self.assertEqual(called_kwargs["title"], "Broadcast Notification")
        self.assertEqual(called_kwargs["content"], "Message for all active users")
        self.assertEqual(called_kwargs["meta"], {"type": "normal", "icon": "system.png"})

    @mock.patch("apps.core.admin_views.broadcast_notification_task")
    def test_broadcast_to_non_existent_user(self, mock_task):
        url = reverse("broadcast")
        response = self.client.post(url, {
            "title": "Missing User",
            "content": "Message for ghost",
            "level": "critical",
            "user_id": 999999,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        mock_task.enqueue.assert_not_called()
        messages_list = list(response.context["messages"])
        self.assertTrue(any("Пользователь с ID 999999 не найден." in str(m) for m in messages_list))


class StaticFilesStorageFallbackTest(SimpleTestCase):
    def test_storage_fallback_on_missing_hashed_file(self):
        from apps.core.staticfiles import StaticFilesStorage

        storage = StaticFilesStorage()
        storage.hashed_files["css/broken.css"] = "css/broken.badhash123.css"

        # The hashed file does not exist on disk, so it must fall back to unhashed clean_name
        result_url = storage.url("./css/broken.css")
        self.assertEqual(result_url, "/staticfiles/css/broken.css")

    def test_storage_normalizes_dot_slash(self):
        from apps.core.staticfiles import StaticFilesStorage

        storage = StaticFilesStorage()
        self.assertEqual(storage.url("./css/main.css"), storage.url("css/main.css"))


@override_settings(ALLOWED_HOSTS=["testserver", "lunastore.app", "ru.lunastore.app"], TRUSTED_PROXIES=["127.0.0.1/32"])
class GeoIPDetectionAndRoutingTest(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.factory = RequestFactory()
        self.geo_config = SimpleNamespace(
            GEO_DOMAIN_PROXY_ENABLED=True,
            GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS=False,
            GEO_DOMAIN_OVERRIDES=json.dumps({
                "RU": {
                    "BASE_URL": "ru.lunastore.app",
                    "API_URL": "//api.ru.lunastore.app",
                    "SPIRE_URL": "//spire.ru.lunastore.app",
                }
            }),
        )
        # Both modules must read the same configuration, independent of the environment.
        for target in ("apps.core.utils.config", "apps.core.middleware.config"):
            patcher = mock.patch(target, self.geo_config)
            patcher.start()
            self.addCleanup(patcher.stop)
        geoip_patcher = mock.patch("apps.core.utils.get_country_code", return_value="Unknown")
        geoip_patcher.start()
        self.addCleanup(geoip_patcher.stop)

    def test_country_from_request_x_country_code(self):
        from apps.core.utils import get_country_from_request

        request = self.factory.get("/", HTTP_X_COUNTRY_CODE="RU")
        self.assertEqual(get_country_from_request(request), "RU")

    def test_country_from_request_cf_ipcountry(self):
        from apps.core.utils import get_country_from_request

        request = self.factory.get("/", HTTP_CF_IPCOUNTRY="KZ")
        self.assertEqual(get_country_from_request(request), "KZ")

    def test_country_from_request_x_geoip_country(self):
        from apps.core.utils import get_country_from_request

        request = self.factory.get("/", HTTP_X_GEOIP_COUNTRY="BY")
        self.assertEqual(get_country_from_request(request), "BY")

    def test_country_from_request_priority(self):
        from apps.core.utils import get_country_from_request

        request = self.factory.get(
            "/",
            HTTP_X_COUNTRY_CODE="RU",
            HTTP_CF_IPCOUNTRY="US",
        )
        self.assertEqual(get_country_from_request(request), "RU")

    @mock.patch("apps.core.utils.get_country_code")
    def test_country_from_request_fallback_and_caching(self, mock_get_code):
        from apps.core.utils import get_country_from_request

        mock_get_code.return_value = "DE"
        request = self.factory.get("/", REMOTE_ADDR="198.51.100.42")

        # first call hits mock
        code1 = get_country_from_request(request)
        self.assertEqual(code1, "DE")
        mock_get_code.assert_called_once_with("198.51.100.42")

        # second call hits cache
        mock_get_code.reset_mock()
        code2 = get_country_from_request(request)
        self.assertEqual(code2, "DE")
        mock_get_code.assert_not_called()

    def test_geo_domains_resolution(self):
        from apps.core.utils import get_geo_domains

        request = self.factory.get("/", HTTP_HOST="ru.lunastore.app")
        domains = get_geo_domains(request)
        self.assertEqual(domains.get("BASE_URL"), "ru.lunastore.app")
        self.assertIn("ru.lunastore.app", domains.get("SPIRE_URL", ""))

    def test_geo_domains_disabled(self):
        from apps.core.utils import get_geo_domains

        request = self.factory.get("/", HTTP_HOST="ru.lunastore.app", HTTP_X_COUNTRY_CODE="RU")
        with mock.patch.object(self.geo_config, "GEO_DOMAIN_PROXY_ENABLED", False):
            self.assertNotIn("BASE_URL", get_geo_domains(request))

    def test_no_redirect_in_django_by_default(self):
        # reverse proxy handles redirects outside django
        response = self.client.get("/index.php", HTTP_X_COUNTRY_CODE="RU")
        self.assertEqual(response.status_code, 200)

    def test_fallback_redirect_middleware_disabled_by_default(self):
        from apps.core.middleware import FallbackGeoRedirectMiddleware

        middleware = FallbackGeoRedirectMiddleware(lambda req: HttpResponse("OK"))
        request = self.factory.get("/index.php", HTTP_X_COUNTRY_CODE="RU", HTTP_HOST="lunastore.app")
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_fallback_redirect_middleware_when_enabled(self):
        from apps.core.middleware import FallbackGeoRedirectMiddleware

        middleware = FallbackGeoRedirectMiddleware(lambda req: HttpResponse("OK"))
        request = self.factory.get("/index.php", HTTP_X_COUNTRY_CODE="RU", HTTP_HOST="lunastore.app")
        with mock.patch.object(self.geo_config, "GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS", True):
            response = middleware(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "http://ru.lunastore.app/index.php")

    def test_country_from_request_sanitization(self):
        from apps.core.utils import get_country_from_request

        for bad in ["XX", "T1", "RUS", "R1", "ru1", "R$", "12", "", "   ", "R\nU"]:
            request = self.factory.get("/", HTTP_X_COUNTRY_CODE=bad)
            self.assertEqual(get_country_from_request(request), "Unknown")

        # valid 2-letter alpha with surrounding whitespace strips cleanly
        request = self.factory.get("/", HTTP_X_COUNTRY_CODE="  RU  ")
        self.assertEqual(get_country_from_request(request), "RU")

    def test_fallback_redirect_skips_current_mirror(self):
        from apps.core.middleware import FallbackGeoRedirectMiddleware

        middleware = FallbackGeoRedirectMiddleware(lambda req: HttpResponse("OK"))
        request = self.factory.get("/index.php", HTTP_X_COUNTRY_CODE="RU", HTTP_HOST="ru.lunastore.app")
        with mock.patch.object(self.geo_config, "GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS", True):
            self.assertEqual(middleware(request).status_code, 200)

    @mock.patch("apps.core.utils.get_country_code")
    def test_country_from_request_spoofing_protection(self, mock_get_code):
        from apps.core.utils import get_country_from_request

        mock_get_code.return_value = "DE"

        # public client ip sends a spoofed header -> header must be ignored and fallback used
        request = self.factory.get("/", HTTP_X_COUNTRY_CODE="US", REMOTE_ADDR="93.184.216.34")
        self.assertEqual(get_country_from_request(request), "DE")
        mock_get_code.assert_called_once_with("93.184.216.34")

        # private / loopback ip sends header -> trusted
        request_local = self.factory.get("/", HTTP_X_COUNTRY_CODE="US", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(get_country_from_request(request_local), "US")

    def test_fallback_redirect_skips_post_and_assets(self):
        from apps.core.middleware import FallbackGeoRedirectMiddleware

        middleware = FallbackGeoRedirectMiddleware(lambda req: HttpResponse("OK"))
        with mock.patch.object(self.geo_config, "GEO_DOMAIN_PYTHON_FALLBACK_REDIRECTS", True):

            # post request should never redirect
            req_post = self.factory.post("/index.php", HTTP_X_COUNTRY_CODE="RU", HTTP_HOST="lunastore.app")
            self.assertEqual(middleware(req_post).status_code, 200)

            # static/media assets should never redirect
            for path in ["/media/test.png", "/staticfiles/js/app.js", "/method/test/"]:
                req_asset = self.factory.get(path, HTTP_X_COUNTRY_CODE="RU", HTTP_HOST="lunastore.app")
                self.assertEqual(middleware(req_asset).status_code, 200)

    def test_geo_domains_normalization(self):
        from apps.core.utils import get_geo_domains

        # test scheme normalization and protocol-relative support
        overrides = json.dumps({
            "RU": {
                "BASE_URL": "https://ru.lunastore.app/",
                "API_URL": "//api.ru.lunastore.app",
                "SPIRE_URL": "//spire.ru.lunastore.app"
            }
        })
        with mock.patch.object(self.geo_config, "GEO_DOMAIN_OVERRIDES", overrides):
            req = self.factory.get("/", HTTP_X_COUNTRY_CODE="RU")
            domains = get_geo_domains(req)
            self.assertEqual(domains["BASE_URL"], "ru.lunastore.app")
            self.assertEqual(domains["API_URL"], "//api.ru.lunastore.app")
            self.assertEqual(domains["SPIRE_URL"], "//spire.ru.lunastore.app")


class TaskPatchesTestCase(SimpleTestCase):
    def setUp(self):
        super().setUp()
        from apps.core.task_patches import patch_redis_tasks_resolver
        patch_redis_tasks_resolver()

    def test_safe_resolve_task_normal(self):
        from django_tasks_redis.backends import RedisTaskBackend

        backend = RedisTaskBackend(alias="default", params={"OPTIONS": {}})
        task = backend._resolve_task("apps.core.tasks.send_telegram_notification")
        self.assertTrue(callable(task) or hasattr(task, "func"))

    def test_safe_resolve_task_synthesizes_flush_analytics(self):
        import apps.analytics.tasks
        from django_tasks_redis.backends import RedisTaskBackend

        orig_attr = getattr(apps.analytics.tasks, "flush_analytics_task", None)
        try:
            if hasattr(apps.analytics.tasks, "flush_analytics_task"):
                delattr(apps.analytics.tasks, "flush_analytics_task")

            backend = RedisTaskBackend(alias="default", params={"OPTIONS": {}})
            with mock.patch("importlib.reload", side_effect=Exception("reload error")):
                task = backend._resolve_task("apps.analytics.tasks.flush_analytics_task")
                self.assertIsNotNone(task)
                result = task.func() if hasattr(task, "func") else task()
                self.assertIsInstance(result, dict)
        finally:
            if orig_attr is not None:
                setattr(apps.analytics.tasks, "flush_analytics_task", orig_attr)

    def test_safe_resolve_task_discards_unknown_task(self):
        from django_tasks_redis.backends import RedisTaskBackend

        backend = RedisTaskBackend(alias="default", params={"OPTIONS": {}})
        task = backend._resolve_task("apps.core.tasks.fictional_unregistered_task")
        self.assertIsNotNone(task)
        result = task.func() if hasattr(task, "func") else task()
        self.assertEqual(result.get("status"), "discarded")
