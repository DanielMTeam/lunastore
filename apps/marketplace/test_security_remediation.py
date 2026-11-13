from types import SimpleNamespace
from unittest.mock import patch

import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.mixins import CDNTokenValidationMixin
from apps.marketplace.admin import ApplicationAdmin
from apps.marketplace.models import Application, Collection, CollectionItem, Distribution
from apps.user.models import User


class CDNConfirmationTests(SimpleTestCase):
    def test_guard_is_bound_to_user_and_upload_target_and_consumed_once(self):
        validator = CDNTokenValidationMixin()
        token = jwt.encode(
            {"type": "cdn-confirm", "guard": "test-guard", "file_id": 5},
            settings.LUNASPIRE_SECRET_KEY, algorithm="HS256",
        )
        cache.set("cdn_guard_101_test-guard", {"object": "screenshot", "mode": "public"}, timeout=60)
        validator.user = SimpleNamespace(pk=102, id=102)
        with self.assertRaises(ValidationError):
            validator.validate_cdn_token(token, expected_object="screenshot", expected_mode="public")
        validator.user = SimpleNamespace(pk=101, id=101)
        with self.assertRaises(ValidationError):
            validator.validate_cdn_token(token, expected_object="icon", expected_mode="public")
        self.assertEqual(
            validator.validate_cdn_token(token, expected_object="screenshot", expected_mode="public")["file_id"], 5,
        )
        with self.assertRaises(ValidationError):
            validator.validate_cdn_token(token, expected_object="screenshot", expected_mode="public")

    def test_existing_screenshot_urls_are_escaped_in_admin(self):
        app = SimpleNamespace(screenshots=["present"], screenshot_urls=['/file" onerror="alert(1)'])
        preview = ApplicationAdmin.display_screenshots(None, app)
        self.assertNotIn(' onerror="alert(1)"', preview)
        self.assertIn("&quot;", preview)


@override_settings(RATELIMIT_BACKEND="memory")
class CatalogVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="catalogowner", email="catalog@example.test")
        cls.private = Application.objects.create(user=cls.owner, title="Private", icon_path="private.png", is_private=True)
        cls.dmca = Application.objects.create(user=cls.owner, title="DMCA", icon_path="dmca.png", is_under_dmca=True)
        cls.private_file = Distribution.objects.create(app=cls.private, version="1", url="https://example.test/private")
        cls.dmca_file = Distribution.objects.create(app=cls.dmca, version="1", url="https://example.test/dmca")
        cls.collection = Collection.objects.create(owner=cls.owner, title="Public", is_public=True)
        for app in (cls.private, cls.dmca):
            CollectionItem.objects.create(collection=cls.collection, application=app)

    def test_download_visibility_is_enforced_before_signing_or_redirecting(self):
        private_url = reverse("download_action", kwargs={"dist_pk": self.private_file.pk})
        dmca_url = reverse("download_action", kwargs={"dist_pk": self.dmca_file.pk})
        self.assertEqual(self.client.get(private_url).status_code, 403)
        self.assertEqual(self.client.get(dmca_url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(private_url).status_code, 302)
        self.assertEqual(self.client.get(dmca_url).status_code, 404)

    def test_existing_public_collection_hides_private_and_dmca_items(self):
        placeholders = ["/staticfiles/img/noavatar_64.jpg"] * 4
        self.assertEqual(self.collection.mosaic_icons(), placeholders)
        response = APIClient().get(f"/method/v2/collection/{self.collection.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items_count"], 0)
        self.assertEqual(response.data["mosaic_icons"], placeholders)

    def test_execute_returns_errors_for_invalid_calls_and_processes_valid_call(self):
        response = APIClient().post("/method/v2/execute/", {
            "code": [None, {"method": []}, {"method": "category.list", "params": []}, {"method": "category.list"}],
        }, format="json")
        self.assertEqual(response.status_code, 200)
        results = response.data["responses"]
        self.assertEqual([item["status"] for item in results[:3]], ["error"] * 3)
        self.assertIn("results", results[3])

    def test_review_limit_runs_before_moderation(self):
        app = Application.objects.create(user=self.owner, title="Public app")
        self.client.force_login(self.owner)
        url = reverse("rate_app")
        for _ in range(60):
            self.client.post(url, {"id": app.pk, "rating": 0})
        with patch("apps.marketplace.views.moderate_review_text") as moderate:
            response = self.client.post(url, {"id": app.pk, "rating": 5, "text": "test"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(app.reviews.exists())
        moderate.assert_not_called()

    def test_private_review_is_denied_before_ai_moderation(self):
        other = User.objects.create_user(username="reviewer", email="reviewer@example.test")
        self.client.force_login(other)
        with patch("apps.marketplace.views.moderate_review_text") as moderate:
            response = self.client.post(reverse("rate_app"), {"id": self.private.pk, "rating": 5, "text": "test"})
        self.assertEqual(response.status_code, 404)
        moderate.assert_not_called()
