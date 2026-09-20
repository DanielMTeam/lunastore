import logging
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.checks import Tags, run_checks
from django.test import TestCase, override_settings
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
