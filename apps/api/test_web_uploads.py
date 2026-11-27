import jwt
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.marketplace.models import Application
from apps.user.models import User


@override_settings(MEILISEARCH_ENABLED=False, LUNASPIRE_SECRET_KEY="web-upload-test-key-32-characters")
class WebUploadMigrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="upload-owner", email="upload-owner@example.test")
        cls.other = User.objects.create_user(username="upload-other", email="upload-other@example.test")
        cls.app = Application.objects.create(user=cls.owner, title="Upload target", is_private=True)

    def test_web_and_admin_use_same_host_session(self):
        for urlconf in ("lunastore.urls", "lunastore.urls_private"):
            with self.subTest(urlconf=urlconf), override_settings(ROOT_URLCONF=urlconf):
                client = APIClient()
                url = reverse("web-public-upload-token")
                self.assertEqual(client.get(url, {"target": "avatar"}).status_code, 403)
                client.force_login(self.owner)
                response = client.get(url, {"target": "avatar"})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertIn("no-store", response["Cache-Control"])
                claims = jwt.decode(response.data["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
                self.assertEqual(claims["user"], str(self.owner.pk))
                self.assertEqual(claims["mode"], "public")
                self.assertEqual(cache.get(f"cdn_guard_{self.owner.pk}_{response.data['guard']}")["mode"], "public")

    def test_private_upload_preserves_app_permission(self):
        with override_settings(ROOT_URLCONF="lunastore.urls_private"):
            url = reverse("web-private-upload-token")
            client = APIClient()
            client.force_login(self.other)
            self.assertEqual(client.get(url, {"app_id": self.app.pk}).status_code, 403)
            client.force_login(self.owner)
            response = client.get(url, {"app_id": self.app.pk})
            self.assertEqual(response.status_code, 200, response.data)
            claims = jwt.decode(response.data["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
            self.assertEqual(claims["object"], str(self.app.pk))
            self.assertEqual(claims["mode"], "private")
