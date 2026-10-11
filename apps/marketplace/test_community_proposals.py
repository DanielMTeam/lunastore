from unittest.mock import Mock, patch

import pyotp
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django_smart_ratelimit.backends.memory import MemoryBackend
from safedelete.models import HARD_DELETE

from apps.marketplace.forms import CommunityAccessConfirmationForm
from apps.marketplace.models import (
    Application, AppEditRequests, Category, Distribution, DistributionCreateRequests, DistributionEditRequests,
)
from apps.marketplace.services.moderation import (
    auto_approve_request, approve_app_edit_request, approve_dist_edit_request,
)
from apps.user.models import User
from apps.marketplace.views import community_access


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CommunityAccessConfirmationTests(SimpleTestCase):
    def setUp(self):
        self.user = User(username="owner")
        self.user.set_password("test-password")

    def test_correct_password_is_required_without_2fa(self):
        self.assertTrue(CommunityAccessConfirmationForm(self.user, {"enabled": "1", "password": "test-password"}).is_valid())
        self.assertFalse(CommunityAccessConfirmationForm(self.user, {"enabled": "1", "password": "wrong"}).is_valid())

    def test_2fa_requires_both_password_and_current_code(self):
        self.user.totp_enabled = True
        self.user.totp_secret = pyotp.random_base32()
        code = pyotp.TOTP(self.user.totp_secret).now()
        self.assertTrue(CommunityAccessConfirmationForm(
            self.user, {"enabled": "1", "password": "test-password", "totp_code": code},
        ).is_valid())
        self.assertFalse(CommunityAccessConfirmationForm(
            self.user, {"enabled": "1", "password": "wrong", "totp_code": code},
        ).is_valid())
        self.assertFalse(CommunityAccessConfirmationForm(
            self.user, {"enabled": "1", "password": "test-password"},
        ).is_valid())

    def test_invalid_2fa_code_and_missing_secret_are_rejected(self):
        self.user.totp_enabled = True
        self.user.totp_secret = pyotp.random_base32()
        self.assertFalse(CommunityAccessConfirmationForm(
            self.user, {"enabled": "1", "password": "test-password", "totp_code": "abcdef"},
        ).is_valid())
        self.user.totp_secret = None
        self.assertFalse(CommunityAccessConfirmationForm(
            self.user, {"enabled": "1", "password": "test-password", "totp_code": "123456"},
        ).is_valid())

    def test_account_without_local_password_cannot_bypass_confirmation(self):
        self.user.set_unusable_password()
        self.assertFalse(CommunityAccessConfirmationForm(self.user, {"enabled": "1", "password": "anything"}).is_valid())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], LANGUAGE_CODE="ru")
class CommunityAccessFeedbackTests(SimpleTestCase):
    def setUp(self):
        self.user = User(pk=1, username="owner")
        self.user.set_password("test-password")
        self.app = Mock(pk=1, user_id=1, allow_community_distributions=False, is_private=False, is_under_dmca=False)
        backend = MemoryBackend()
        self.addCleanup(backend.shutdown)

        def get_confirmation_object(queryset, **kwargs):
            return self.user if "is_active" in kwargs else self.app

        for target, options in (
            ("django_smart_ratelimit.decorator.get_backend", {"return_value": backend}),
            ("django.db.transaction.Atomic.__enter__", {"return_value": None}),
            ("django.db.transaction.Atomic.__exit__", {"return_value": False}),
            ("apps.marketplace.views.get_object_or_404", {"side_effect": get_confirmation_object}),
        ):
            patcher = patch(target, **options)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("apps.marketplace.views.render", side_effect=lambda request, template, context, **kw:
                        HttpResponse(status=kw.get("status", 200)))
        self.render = patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, method="post", data=None):
        request = getattr(RequestFactory(), method)("/community_access.php/1/", data or {})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_password_and_2fa_errors_are_sent_to_messages(self):
        self.user.totp_enabled = True
        self.user.totp_secret = pyotp.random_base32()
        request = self.request(data={"password": "wrong", "enabled": "1", "totp_code": "invalid"})
        response = community_access(request, pk=1)
        self.assertEqual(response.status_code, 200)
        form = self.render.call_args.args[2]["form"]
        expected = [str(error) for errors in form.errors.values() for error in errors]
        actual = list(get_messages(request))
        self.assertEqual([str(message) for message in actual], expected)
        self.assertTrue(all(message.tags == "error" for message in actual))
        self.app.save.assert_not_called()

    def test_public_app_requirement_is_sent_to_messages(self):
        self.app.is_private = True
        request = self.request(data={"password": "test-password", "enabled": "1"})
        self.assertEqual(community_access(request, pk=1).status_code, 200)
        self.assertEqual(len(list(get_messages(request))), 1)
        self.app.save.assert_not_called()

    def test_gets_do_not_consume_confirmation_limit_and_blocked_posts_do_not_validate(self):
        for _ in range(10):
            self.assertEqual(community_access(self.request("get"), pk=1).status_code, 200)
        for _ in range(5):
            request = self.request(data={"password": "wrong", "enabled": "1"})
            self.assertEqual(community_access(request, pk=1).status_code, 200)
        request = self.request(data={"password": "test-password", "enabled": "1"})
        with patch.object(CommunityAccessConfirmationForm, "is_valid") as validate:
            response = community_access(request, pk=1)
        self.assertEqual(response.status_code, 429)
        validate.assert_not_called()
        self.assertEqual(len(list(get_messages(request))), 1)
        self.assertIn("Retry-After", response)
        self.app.save.assert_not_called()
        self.assertEqual(community_access(self.request("get"), pk=1).status_code, 200)


@override_settings(
    ROOT_URLCONF="lunastore.urls", TELEGRAM_LOGGER_ENABLED=False, MEILISEARCH_ENABLED=False,
    LANGUAGE_CODE="ru", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
                "django.contrib.messages.middleware.MessageMiddleware"],
)
class CommunityProposalTests(TestCase):
    def setUp(self):
        cache.clear()
        backend = MemoryBackend()
        self.addCleanup(backend.shutdown)
        backend_patch = patch("django_smart_ratelimit.decorator.get_backend", return_value=backend)
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        self.owner = User.objects.create_user("owner", "owner@example.test", "test-password")
        self.contributor = User.objects.create_user("contributor", "contributor@example.test", "test-password")
        self.contributor.is_trusted = True
        self.contributor.save()
        group = Group.objects.get(name="Разработчики")
        self.owner.groups.add(group)
        self.contributor.groups.add(group)
        self.app = Application.objects.create(user=self.owner, title="Original", description="Description")
        self.dist = Distribution.objects.create(app=self.app, version="1.0", url="https://example.test/app.zip")
        self.access_url = reverse("community_access", kwargs={"pk": self.app.pk})
        self.edit_url = reverse("edit_app_info", kwargs={"pk": self.app.pk})
        self.client.force_login(self.owner)

    def enable(self):
        response = self.client.post(self.access_url, {"enabled": "1", "password": "test-password"})
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()

    def proposal(self):
        return AppEditRequests.objects.create(
            user=self.contributor, target_application=self.app, title="Proposed", description="New description",
            is_private=True, allow_reviews=False, allow_community_distributions=False,
        )

    def test_activation_requires_password_and_cannot_be_used_by_other_users(self):
        self.assertEqual(self.client.post(self.access_url, {"enabled": "1", "password": "wrong"}).status_code, 200)
        self.app.refresh_from_db()
        self.assertFalse(self.app.community_protected)
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.post(self.access_url, {"enabled": "1", "password": "test-password"}).status_code, 403)

    def test_activation_requires_2fa_when_enabled(self):
        self.owner.totp_enabled = True
        self.owner.totp_secret = pyotp.random_base32()
        self.owner.save()
        self.client.post(self.access_url, {"enabled": "1", "password": "test-password"})
        self.app.refresh_from_db()
        self.assertFalse(self.app.community_protected)
        self.assertEqual(self.client.post(self.access_url, {
            "enabled": "1", "password": "test-password", "totp_code": pyotp.TOTP(self.owner.totp_secret).now(),
        }).status_code, 302)
        self.app.refresh_from_db()
        self.assertTrue(self.app.community_protected)

    def test_confirmation_reloads_2fa_enabled_after_user_was_authenticated(self):
        User.objects.filter(pk=self.owner.pk).update(totp_enabled=True, totp_secret=pyotp.random_base32())
        request = RequestFactory().post(self.access_url, {"enabled": "1", "password": "test-password"})
        request.user = self.owner  # Authenticated object predates the 2FA update.
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        response = community_access(request, pk=self.app.pk)
        self.assertEqual(response.status_code, 200)
        self.app.refresh_from_db()
        self.assertFalse(self.app.community_protected)

    def test_inactive_contributor_cannot_have_proposal_approved(self):
        self.enable()
        req = self.proposal()
        User.objects.filter(pk=self.contributor.pk).update(is_active=False)
        self.assertIsNone(approve_app_edit_request(req, actor=self.owner))

    def test_private_app_cannot_enable_mode(self):
        self.app.is_private = True
        self.app.save()
        self.client.post(self.access_url, {"enabled": "1", "password": "test-password"})
        self.app.refresh_from_db()
        self.assertFalse(self.app.allow_community_distributions)

    def test_disabling_keeps_permanent_protection(self):
        self.enable()
        self.client.post(self.access_url, {"enabled": "0", "password": "test-password"})
        self.app.refresh_from_db()
        self.assertFalse(self.app.allow_community_distributions)
        self.assertTrue(self.app.community_protected)
        for policy in (None, HARD_DELETE):
            with self.assertRaises(ProtectedError):
                self.app.delete(force_policy=policy)
            with self.assertRaises(ProtectedError):
                Application.objects.filter(pk=self.app.pk).delete(force_policy=policy)

    def test_stale_application_instance_cannot_bypass_deletion_protection(self):
        stale_app = Application.objects.get(pk=self.app.pk)
        self.enable()
        with self.assertRaises(ProtectedError):
            stale_app.delete(force_policy=HARD_DELETE)

    def test_stale_save_cannot_remove_permanent_protection(self):
        stale_app = Application.objects.get(pk=self.app.pk)
        self.enable()
        stale_app.title = "Stale save"
        stale_app.save()
        self.app.refresh_from_db()
        self.assertTrue(self.app.community_protected)

    def test_retained_application_is_reindexed_after_owner_deletion_commit(self):
        self.enable()
        with override_settings(MEILISEARCH_ENABLED=True):
            with patch("apps.core.search.signals.sync_application_task") as task:
                with self.captureOnCommitCallbacks(execute=True):
                    with patch("apps.core.search.signals.sync_user_task"):
                        self.owner.delete(force_policy=HARD_DELETE)
                task.enqueue.assert_called_once_with(self.app.pk, using="default")

    def test_owner_account_soft_delete_preserves_app_and_distribution(self):
        self.enable()
        self.owner.delete()
        self.app.refresh_from_db()
        self.dist.refresh_from_db()
        self.assertIsNone(self.app.user_id)
        self.assertIsNone(self.app.deleted)
        self.assertIsNone(self.dist.deleted)

    def test_owner_account_hard_delete_preserves_only_protected_apps(self):
        ordinary = Application.objects.create(user=self.owner, title="Ordinary")
        self.enable()
        self.owner.delete(force_policy=HARD_DELETE)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.user_id)
        self.assertTrue(Distribution.objects.filter(pk=self.dist.pk).exists())
        self.assertFalse(Application.objects.all_with_deleted().filter(pk=ordinary.pk).exists())
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.get(reverse("app"), {"id": self.app.pk}).status_code, 200)
        self.assertEqual(self.client.get(reverse("download"), {"id": self.app.pk}).status_code, 200)
        self.assertEqual(self.client.get(self.edit_url).status_code, 200)

    def test_bulk_owner_deletion_preserves_app(self):
        self.enable()
        User.objects.filter(pk=self.owner.pk).delete(force_policy=HARD_DELETE)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.user_id)
        self.assertTrue(Distribution.objects.filter(pk=self.dist.pk).exists())

    def test_trusted_contributor_always_requires_manual_moderation(self):
        self.enable()
        req = self.proposal()
        self.assertIsNone(auto_approve_request(req))
        self.app.refresh_from_db()
        self.assertEqual(self.app.title, "Original")
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_app_edit_request(req, actor=self.owner))
        self.app.refresh_from_db()
        self.assertEqual(self.app.title, "Proposed")
        self.assertFalse(self.app.is_private)
        self.assertTrue(self.app.allow_reviews)
        self.assertTrue(self.app.allow_community_distributions)
        self.assertEqual(self.app.user_id, self.owner.pk)
        self.assertIsNone(approve_app_edit_request(req))

    def test_disabled_and_stale_proposals_cannot_be_approved(self):
        self.enable()
        req = self.proposal()
        self.app.title = "Owner updated"
        self.app.save()
        self.assertIsNone(approve_app_edit_request(req))
        req = self.proposal()
        self.app.allow_community_distributions = False
        self.app.save()
        self.assertIsNone(approve_app_edit_request(req))

    def test_community_edit_form_hides_access_settings_and_caps_pending_requests(self):
        self.enable()
        self.client.force_login(self.contributor)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("is_private", response.context["form"].fields)
        self.assertNotIn("allow_reviews", response.context["form"].fields)
        self.assertNotIn("allow_community_distributions", response.context["form"].fields)
        self.proposal()
        self.assertEqual(self.client.post(self.edit_url, {}).status_code, 302)
        self.assertEqual(AppEditRequests.objects.filter(target_application=self.app).count(), 1)

    def test_distribution_proposal_remains_pending_until_moderator_approves(self):
        self.enable()
        self.client.force_login(self.contributor)
        url = reverse("distribution_edit", kwargs={"dist_pk": self.dist.pk})
        self.assertEqual(self.client.post(url, {
            "version": "2.0", "url": "https://example.test/new.zip", "lunabox_type": "file",
        }).status_code, 302)
        req = DistributionEditRequests.objects.get(target_distribution=self.dist)
        self.assertEqual(req.status, "pending")
        self.dist.refresh_from_db()
        self.assertEqual(self.dist.version, "1.0")
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_dist_edit_request(req, actor=self.owner))
        self.dist.refresh_from_db()
        self.assertEqual(self.dist.version, "2.0")

    def test_non_developer_cannot_edit_community_app(self):
        self.enable()
        self.contributor.groups.clear()
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)

    def edit_data(self):
        category = Category.objects.create(name="Utilities")
        return {
            "title_ru": "Proposed", "description_ru": "New description", "slogan_ru": "New slogan",
            "price": "0", "categories": [category.pk], "allow_community_distributions": "on",
            "is_private": "on", "allow_reviews": "", "community_protected": "",
        }

    def test_forged_owner_edit_cannot_activate_mode(self):
        data = self.edit_data()
        response = self.client.post(self.edit_url, data)
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()
        self.assertFalse(self.app.allow_community_distributions)
        self.assertFalse(self.app.community_protected)

    def test_contributor_post_only_creates_pending_proposal_and_ignores_access_flags(self):
        self.enable()
        self.client.force_login(self.contributor)
        response = self.client.post(self.edit_url, self.edit_data())
        self.assertEqual(response.status_code, 302)
        req = AppEditRequests.objects.get(target_application=self.app)
        self.assertEqual(req.status, "pending")
        self.app.refresh_from_db()
        self.assertEqual(self.app.title, "Original")
        self.assertTrue(self.app.allow_reviews)
        self.assertFalse(req.is_private)
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_app_edit_request(req, actor=self.owner))
        self.app.refresh_from_db()
        self.assertFalse(self.app.is_private)
        self.assertTrue(self.app.allow_reviews)
        self.assertTrue(self.app.community_protected)

    def test_distribution_create_caps_pending_proposals_per_author(self):
        self.enable()
        self.client.force_login(self.contributor)
        url = reverse("distribution_create", kwargs={"app_id": self.app.pk})
        data = {"version": "2.0", "url": "https://example.test/new.zip", "lunabox_type": "file"}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(DistributionCreateRequests.objects.filter(app=self.app, user=self.contributor).count(), 1)

    @patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info")
    def test_screenshot_token_payload_must_be_a_bounded_list(self, file_info):
        import json
        for payload in ({"token": "bad"}, None, ["bad"] * 100):
            data = self.edit_data()
            data["cdn_screenshots_tokens"] = json.dumps(payload)
            self.assertEqual(self.client.post(self.edit_url, data).status_code, 200)
        self.assertFalse(AppEditRequests.objects.filter(target_application=self.app).exists())
        file_info.assert_not_called()
