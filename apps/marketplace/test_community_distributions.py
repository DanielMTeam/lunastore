from unittest.mock import patch

import jwt
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override
from django_smart_ratelimit.backends.memory import MemoryBackend
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.marketplace.models import Application, Distribution, DistributionCreateRequests
from apps.user.models import User


@override_settings(
    ROOT_URLCONF="lunastore.urls",
    TELEGRAM_LOGGER_ENABLED=False,
    MEILISEARCH_ENABLED=False,
    LANGUAGE_CODE="ru",
    LUNASPIRE_SECRET_KEY="community-distribution-test-secret",
    LUNASPIRE_URL="//spire.example.test",
    MIDDLEWARE=[
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
)
class CommunityDistributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="owner", email="owner@example.test")
        cls.developer = User.objects.create(username="contributor", email="contributor@example.test")
        cls.regular = User.objects.create(username="regular", email="regular@example.test")
        cls.staff = User.objects.create(username="staff", email="staff@example.test", is_staff=True)
        cls.superuser = User.objects.create(username="superuser", email="superuser@example.test", is_superuser=True)
        group = Group.objects.get(name="Разработчики")
        cls.owner.groups.add(group)
        cls.developer.groups.add(group)
        cls.app = Application.objects.create(
            user=cls.owner,
            title="Community app",
            description="Test application",
            allow_community_distributions=True,
        )

    def setUp(self):
        cache.clear()
        # The decorator keeps its backend configuration from import time.
        backend = MemoryBackend()
        self.addCleanup(backend.shutdown)
        backend_patch = patch("django_smart_ratelimit.decorator.get_backend", return_value=backend)
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        self.client.force_login(self.developer)
        self.create_url = reverse("distribution_create", kwargs={"app_id": self.app.pk})
        self.token_url = reverse("user-get-private-upload-token")
        self.download_url = reverse("download") + f"?id={self.app.pk}"
        self.data = {"version": "1.0", "url": "https://example.test/app.zip", "lunabox_type": "file"}

    def test_create_form_has_upload_configuration(self):
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["get_token_url"], self.token_url)
        self.assertEqual(response.context["cdn_upload_url"], "//spire.example.test/cdn/upload")
        self.assertContains(response, f'href="{self.download_url}"')

    def test_owner_is_redirected_to_distribution_management(self):
        self.client.force_login(self.owner)
        self.assertRedirects(
            self.client.get(self.create_url),
            reverse("manage_distributions") + f"?id={self.app.pk}",
            fetch_redirect_response=False,
        )

    def test_owner_distribution_editor_keeps_upload_configuration(self):
        distribution = Distribution.objects.create(app=self.app, version="1.0", url=self.data["url"])
        self.client.force_login(self.owner)
        response = self.client.get(reverse("distribution_edit", kwargs={"dist_pk": distribution.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["get_token_url"], self.token_url)
        self.assertEqual(response.context["cdn_upload_url"], "//spire.example.test/cdn/upload")

    def test_developer_can_submit_external_distribution_for_moderation(self):
        self.assertRedirects(self.client.post(self.create_url, self.data), self.download_url)
        req = DistributionCreateRequests.objects.get(app=self.app)
        self.assertEqual(req.user, self.developer)
        self.assertEqual(req.status, "pending")
        self.assertFalse(Distribution.objects.filter(app=self.app).exists())

    def test_private_app_rejects_get_post_and_upload_token(self):
        self.app.is_private = True
        self.app.save()
        self.assertEqual(self.client.get(self.create_url).status_code, 403)
        self.assertEqual(self.client.post(self.create_url, self.data).status_code, 403)
        self.assertEqual(self.client.get(self.token_url, {"app_id": self.app.pk}).status_code, 403)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    def test_disabled_community_distributions_reject_get_post_and_token(self):
        self.app.allow_community_distributions = False
        self.app.save()
        with override("ru"):
            response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Сторонние дистрибуции", status_code=403)
        self.assertNotContains(response, "COMMUNITY_DISTRIBUTIONS_ARE_NOT_ALLOWED", status_code=403)
        self.assertEqual(self.client.post(self.create_url, self.data).status_code, 403)
        self.assertEqual(self.client.get(self.token_url, {"app_id": self.app.pk}).status_code, 403)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    def test_regular_user_cannot_submit_or_get_token_and_has_no_add_link(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.post(self.create_url, self.data).status_code, 302)
        self.assertEqual(self.client.get(self.token_url, {"app_id": self.app.pk}).status_code, 403)
        self.assertNotContains(self.client.get(self.download_url), f'href="{self.create_url}"')
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    def test_anonymous_user_has_no_add_link_and_cannot_submit(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.create_url, self.data).status_code, 302)
        self.assertNotContains(self.client.get(self.download_url), f'href="{self.create_url}"')
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    def test_developer_has_add_link_and_receives_upload_token(self):
        self.assertContains(self.client.get(self.download_url), f'href="{self.create_url}"')
        response = self.client.get(self.token_url, {"app_id": self.app.pk})
        self.assertEqual(response.status_code, 200)
        payload = jwt.decode(response.json()["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(payload["object"], str(self.app.pk))
        self.assertEqual(payload["user"], str(self.developer.pk))
        self.assertEqual(payload["mode"], "private")

    def test_existing_owner_and_staff_upload_permissions_are_preserved(self):
        self.app.is_private = True
        self.app.allow_community_distributions = False
        self.app.save()
        for user in (self.owner, self.staff):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.token_url, {"app_id": self.app.pk}).status_code, 200)

    def test_superuser_can_submit_public_community_distribution(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.create_url).status_code, 200)
        self.assertEqual(self.client.get(self.token_url, {"app_id": self.app.pk}).status_code, 200)

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info", return_value={"hash": "test-hash"})
    def test_uploaded_file_confirmation_creates_pending_request(self, mock_file_info):
        response = self.client.get(self.token_url, {"app_id": self.app.pk})
        payload = jwt.decode(response.json()["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
        # LunaSpire confirmation contains the guard and file ID, not upload claims.
        payload = {"type": "cdn-confirm", "file_id": 123, "guard": payload["guard"], "exp": payload["exp"]}
        self.data.update(
            url="",
            cdn_confirm_token=jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"),
            virustotal_url="https://www.virustotal.com/gui/file/test-hash",
        )
        self.assertRedirects(self.client.post(self.create_url, self.data), self.download_url)
        req = DistributionCreateRequests.objects.get(app=self.app)
        self.assertEqual(req.cdn_file_id, 123)
        self.assertEqual(req.cdn_hash, "test-hash")
        self.assertEqual(req.status, "pending")
        mock_file_info.assert_called_once_with(123, fields="hash")

    def upload_data(self, payload):
        return {
            **self.data, "url": "", "virustotal_url": "https://www.virustotal.com/gui/file/test-hash",
            "cdn_confirm_token": jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256"),
        }

    def confirmation(self, app_id=None):
        response = self.client.get(self.token_url, {"app_id": app_id or self.app.pk})
        upload = jwt.decode(response.json()["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
        return {"type": "cdn-confirm", "file_id": 123, "guard": upload["guard"], "exp": upload["exp"]}

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info", return_value={"hash": "test-hash"})
    def test_owner_upload_uses_guard_and_rejects_replay(self, file_info):
        self.client.force_login(self.owner)
        url = reverse("manage_distributions") + f"?id={self.app.pk}"
        data = self.upload_data(self.confirmation())
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(DistributionCreateRequests.objects.filter(app=self.app).count(), 1)
        file_info.assert_called_once()

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info")
    def test_token_for_another_app_cannot_be_attached(self, file_info):
        other_app = Application.objects.create(user=self.developer, title="Other app")
        self.assertEqual(self.client.post(self.create_url, self.upload_data(self.confirmation(other_app.pk))).status_code, 200)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())
        file_info.assert_not_called()

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info")
    def test_confirmation_from_another_user_cannot_be_reused_by_owner(self, file_info):
        payload = self.confirmation()
        self.client.force_login(self.owner)
        url = reverse("manage_distributions") + f"?id={self.app.pk}"
        self.assertEqual(self.client.post(url, self.upload_data(payload)).status_code, 200)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())
        file_info.assert_not_called()

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info")
    def test_public_media_token_cannot_be_used_as_distribution(self, file_info):
        guard = "public-media-guard"
        cache.set(f"cdn_guard_{self.developer.pk}_{guard}", True)
        payload = {"type": "cdn-confirm", "file_id": 123, "guard": guard}
        self.assertEqual(self.client.post(self.create_url, self.upload_data(payload)).status_code, 200)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())
        file_info.assert_not_called()

    def test_cdn_validation_holds_no_app_lock_and_rechecks_disabled_access(self):
        data = self.upload_data(self.confirmation())
        with CaptureQueriesContext(connection) as queries:
            def file_info(*args, **kwargs):
                self.assertFalse(any("FOR UPDATE" in query["sql"] for query in queries))
                Application.objects.filter(pk=self.app.pk).update(allow_community_distributions=False)
                return {"hash": "test-hash"}

            with patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info", side_effect=file_info):
                self.assertEqual(self.client.post(self.create_url, data).status_code, 403)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info", return_value={"hash": "test-hash"})
    def test_v2_upload_token_is_compatible_with_distribution_confirmation(self, file_info):
        from apps.api.v2.views import UserViewSet
        request = APIRequestFactory().get("/v2/user/getPrivateUploadToken/", {"app_id": self.app.pk})
        force_authenticate(request, user=self.developer)
        response = UserViewSet.as_view({"get": "get_private_upload_token"})(request)
        self.assertEqual(response.status_code, 200)
        upload = jwt.decode(response.data["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
        payload = {"type": "cdn-confirm", "file_id": 123, "guard": upload["guard"], "exp": upload["exp"]}
        self.assertEqual(self.client.post(self.create_url, self.upload_data(payload)).status_code, 302)
        self.assertEqual(DistributionCreateRequests.objects.get(app=self.app).cdn_file_id, 123)

    def test_v2_regular_user_and_private_app_cannot_get_community_upload_token(self):
        from apps.api.v2.views import UserViewSet
        view = UserViewSet.as_view({"get": "get_private_upload_token"})
        request = APIRequestFactory().get("/v2/user/getPrivateUploadToken/", {"app_id": self.app.pk})
        force_authenticate(request, user=self.regular)
        self.assertEqual(view(request).status_code, 403)
        self.app.is_private = True
        self.app.save()
        request = APIRequestFactory().get("/v2/user/getPrivateUploadToken/", {"app_id": self.app.pk})
        force_authenticate(request, user=self.developer)
        self.assertEqual(view(request).status_code, 403)

    def test_pending_request_author_remains_visible_when_community_uploads_are_disabled(self):
        DistributionCreateRequests.objects.create(
            app=self.app, user=self.developer, version="1.0", url=self.data["url"],
        )
        self.app.allow_community_distributions = False
        self.app.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("manage_distributions"), {"id": self.app.pk})
        self.assertEqual(response.context["get_token_url"], self.token_url)
        self.assertEqual(response.context["cdn_upload_url"], "//spire.example.test/cdn/upload")
        self.assertContains(response, f'href="{reverse("profile")}?id={self.developer.pk}"')
        self.assertContains(response, self.developer.username)
