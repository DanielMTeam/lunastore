"""Authorization regressions for per-application delegation."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import IntegrityError, transaction, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from django_smart_ratelimit.backends.memory import MemoryBackend
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.marketplace.models import (
    Application, ApplicationAccess, AppEditRequests, Category, Distribution,
    DistributionCreateRequests, DistributionEditRequests,
)
from apps.marketplace.services.access import application_role, can_manage_app, set_application_access
from apps.marketplace.services.moderation import (
    approve_app_edit_request, approve_dist_create_request, approve_dist_edit_request, auto_approve_request,
)
from apps.user.models import User, UserBan


@override_settings(
    ROOT_URLCONF="lunastore.urls", TELEGRAM_LOGGER_ENABLED=False, MEILISEARCH_ENABLED=False,
    LANGUAGE_CODE="ru", LUNASPIRE_SECRET_KEY="application-access-test-secret-32-bytes",
    LUNASPIRE_URL="//spire.example.test",
    MIDDLEWARE=[
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
)
class ApplicationAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", "owner@example.test", "password")
        cls.admin = User.objects.create_user("appadmin", "admin@example.test", "password")
        cls.editor = User.objects.create_user("editor", "editor@example.test", "password")
        cls.other = User.objects.create_user("other", "other@example.test", "password")
        cls.app = Application.objects.create(user=cls.owner, title="Test app", description="Description")
        cls.second = Application.objects.create(user=cls.owner, title="Second app")
        cls.dist = Distribution.objects.create(app=cls.app, version="1.0", url="https://example.test/app.zip")
        cls.category = Category.objects.create(name="Tools")
        for user, role in ((cls.admin, "admin"), (cls.editor, "editor")):
            ApplicationAccess.objects.create(application=cls.app, user=user, role=role, granted_by=cls.owner)

    def setUp(self):
        cache.clear()
        backend = MemoryBackend()
        self.addCleanup(backend.shutdown)
        patcher = patch("django_smart_ratelimit.decorator.get_backend", return_value=backend)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(self.owner)

    def edit_data(self, **extra):
        return {
            "title_ru": "Updated", "description_ru": "New description", "price": "0",
            "categories": [self.category.pk], **extra,
        }

    def app_request(self, user=None, origin="admin", **extra):
        return AppEditRequests.objects.create(
            target_application=self.app, user=user or self.admin, request_origin=origin,
            title="Updated", description="New description", **extra,
        )

    def test_capability_matrix_and_application_isolation(self):
        for user, expected in (
            (self.owner, (True, True, True)), (self.admin, (True, True, False)),
            (self.editor, (True, False, False)), (self.other, (False, False, False)),
            (AnonymousUser(), (False, False, False)),
        ):
            with self.subTest(user=user):
                self.assertEqual(tuple(can_manage_app(self.app, user, cap) for cap in ("info", "files", "rights")), expected)
        self.assertFalse(can_manage_app(self.second, self.admin))
        self.assertFalse(can_manage_app(self.second, self.editor))

    def test_banned_inactive_and_deleted_accounts_have_no_access(self):
        ban = UserBan.objects.create(user=self.admin, is_permanent=True, reason="Test")
        self.assertIsNone(application_role(self.app, self.admin))
        ban.is_permanent = False
        ban.expires_at = timezone.now() - timedelta(seconds=1)
        ban.save()
        self.assertEqual(application_role(self.app, self.admin), "admin")
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertIsNone(application_role(self.app, self.admin))
        User.objects.filter(pk=self.admin.pk).update(is_active=True, deleted=timezone.now())
        self.assertIsNone(application_role(self.app, self.admin))

    def test_owner_can_add_change_and_revoke_without_duplicates(self):
        url = reverse("app_rights_add", kwargs={"pk": self.app.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
        for role in ("editor", "admin", "admin"):
            self.assertEqual(self.client.post(url, {"username": self.other.username, "role": role}).status_code, 302)
        self.assertEqual(ApplicationAccess.objects.filter(application=self.app, user=self.other).count(), 1)
        edit = reverse("app_rights_edit", kwargs={"pk": self.app.pk, "user_id": self.other.pk})
        self.assertEqual(self.client.post(edit, {"role": "none"}).status_code, 302)
        self.assertFalse(ApplicationAccess.objects.filter(application=self.app, user=self.other).exists())
        self.assertTrue(LogEntry.objects.filter(change_message__contains="Application access:").exists())

    def test_owner_unknown_user_and_invalid_role_are_rejected(self):
        url = reverse("app_rights_add", kwargs={"pk": self.app.pk})
        for data in (
            {"username": self.owner.username, "role": "admin"},
            {"username": "missing", "role": "editor"},
            {"username": self.other.username, "role": "owner"},
        ):
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertFalse(ApplicationAccess.objects.filter(user=self.owner).exists())

    def test_only_owner_can_manage_members(self):
        for user in (self.admin, self.editor, self.other):
            self.client.force_login(user)
            for route in ("app_rights", "app_rights_add"):
                url = reverse(route, kwargs={"pk": self.app.pk})
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"username": self.other.username, "role": "admin"}).status_code, 403)

    def test_csrf_and_get_do_not_change_membership(self):
        url = reverse("app_rights_add", kwargs={"pk": self.app.pk})
        self.client.get(url, {"username": self.other.username, "role": "admin"})
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(url, {"username": self.other.username, "role": "admin"}).status_code, 403)
        self.assertFalse(ApplicationAccess.objects.filter(user=self.other).exists())

    def test_database_rejects_duplicate_and_unknown_roles(self):
        for role in ("admin", "owner"):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ApplicationAccess.objects.create(application=self.app, user=self.admin if role == "admin" else self.other, role=role)

    def test_delegated_apps_and_role_in_settings(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("settings_apps"))
        self.assertEqual(list(response.context["managed_apps"]), [self.app])
        self.assertContains(response, "Редактор")
        self.assertNotContains(response, "Second app")

    def test_settings_survives_revocation_after_app_query(self):
        self.client.force_login(self.editor)
        revoked = False

        def revoke_after_app_query(execute, sql, params, many, context):
            nonlocal revoked
            result = execute(sql, params, many, context)
            if not revoked and sql.startswith("SELECT") and 'FROM "marketplace_application"' in sql:
                revoked = True
                set_application_access(self.app.pk, self.owner, self.editor, "none")
            return result

        with connections["default"].execute_wrapper(revoke_after_app_query):
            response = self.client.get(reverse("settings_apps"))
        self.assertTrue(revoked)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("settings_apps"))
        self.assertEqual(list(response.context["managed_apps"]), [])

    def test_editor_form_hides_files_screenshots_settings_and_rights(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("edit_app_info", kwargs={"pk": self.app.pk}))
        self.assertEqual(response.status_code, 200)
        for field in ("is_private", "allow_reviews", "upload_screenshots", "cdn_screenshots_tokens"):
            self.assertNotIn(field, response.context["form"].fields)
        for route in ("app_rights", "community_access"):
            self.assertNotContains(response, reverse(route, kwargs={"pk": self.app.pk}))
        self.assertNotContains(response, 'id="screenshots-interactive-container"')

    def test_editor_forged_fields_cannot_change_screenshots_or_settings(self):
        self.app.screenshots = ["screenshots/original.png"]
        self.app.save()
        self.client.force_login(self.editor)
        response = self.client.post(reverse("edit_app_info", kwargs={"pk": self.app.pk}), self.edit_data(
            is_private="on", allow_reviews="", cdn_screenshots_data='["forged.png"]',
            cdn_screenshots_tokens='["invalid-token"]', allow_community_distributions="on",
        ))
        self.assertEqual(response.status_code, 302)
        req = AppEditRequests.objects.get(target_application=self.app)
        self.assertEqual(req.request_origin, "editor")
        self.assertEqual(req.screenshots, ["screenshots/original.png"])
        self.app.screenshots = ["screenshots/current.png"]
        self.app.is_private = True
        self.app.allow_reviews = False
        self.app.save()
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_app_edit_request(req, actor=self.owner))
        self.app.refresh_from_db()
        self.assertEqual(self.app.screenshots, ["screenshots/current.png"])
        self.assertTrue(self.app.is_private)
        self.assertFalse(self.app.allow_reviews)
        self.assertFalse(self.app.allow_community_distributions)

    def test_editor_cannot_manage_distributions_even_with_developer_status(self):
        self.client.force_login(self.editor)
        for url in (
            reverse("manage_distributions") + f"?id={self.app.pk}",
            reverse("distribution_edit", kwargs={"dist_pk": self.dist.pk}),
            reverse("distribution_create", kwargs={"app_id": self.app.pk}),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("distribution_delete", kwargs={"dist_pk": self.dist.pk})).status_code, 403)

    def test_admin_without_developer_status_can_submit_release(self):
        self.client.force_login(self.admin)
        url = reverse("manage_distributions") + f"?id={self.app.pk}"
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"version": "2.0", "url": "https://example.test/new.zip", "lunabox_type": "file"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DistributionCreateRequests.objects.get(app=self.app).request_origin, "admin")

    def test_distribution_delete_requires_post_and_admin_role(self):
        self.client.force_login(self.admin)
        url = reverse("distribution_delete", kwargs={"dist_pk": self.dist.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(Distribution.objects.filter(pk=self.dist.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Distribution.objects.filter(pk=self.dist.pk).exists())

    def test_stats_for_both_roles(self):
        with patch("apps.marketplace.views.get_app_analytics", return_value={}):
            for user in (self.admin, self.editor):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("app_stats", kwargs={"pk": self.app.pk})).status_code, 200)

    def test_revoke_rejects_all_delegated_requests_and_regrant_does_not_restore(self):
        app_req = self.app_request()
        create = DistributionCreateRequests.objects.create(app=self.app, user=self.admin, version="2", request_origin="admin")
        edit = DistributionEditRequests.objects.create(app=self.app, target_distribution=self.dist, user=self.admin, version="3", request_origin="admin")
        set_application_access(self.app.pk, self.owner, self.admin, "none")
        set_application_access(self.app.pk, self.owner, self.admin, "admin")
        for req, approve in ((app_req, approve_app_edit_request), (create, approve_dist_create_request), (edit, approve_dist_edit_request)):
            req.refresh_from_db()
            self.assertEqual(req.status, "rejected")
            self.assertIsNone(approve(req, actor=self.owner))

    def test_downgrade_rejects_admin_requests_but_not_editor_requests(self):
        req = self.app_request()
        editor_req = self.app_request(origin="editor")
        set_application_access(self.app.pk, self.owner, self.admin, "editor")
        req.refresh_from_db()
        editor_req.refresh_from_db()
        self.assertEqual(req.status, "rejected")
        self.assertEqual(editor_req.status, "pending")

    def test_approval_rechecks_role_even_if_membership_changed_outside_service(self):
        req = self.app_request()
        ApplicationAccess.objects.filter(user=self.admin).delete()
        self.app.allow_community_distributions = True
        self.app.save()
        self.assertIsNone(approve_app_edit_request(req, actor=self.owner))

    def test_trusted_delegated_author_uses_existing_autoapproval(self):
        self.admin.is_trusted = True
        self.admin.save()
        req = self.app_request()
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(auto_approve_request(req))

    def test_private_upload_tokens_v1_v2_respect_roles_and_revocation(self):
        from apps.api.views import UserViewSet
        from apps.api.v2.views import UserViewSet as UserViewSetV2
        self.app.is_private = True
        self.app.save()
        for viewset in (UserViewSet, UserViewSetV2):
            for user, status in ((self.owner, 200), (self.admin, 200), (self.editor, 403), (self.other, 403)):
                request = APIRequestFactory().get("/token", {"app_id": self.app.pk})
                force_authenticate(request, user)
                self.assertEqual(viewset.as_view({"get": "get_private_upload_token"})(request).status_code, status)
        set_application_access(self.app.pk, self.owner, self.admin, "none")
        request = APIRequestFactory().get("/token", {"app_id": self.app.pk})
        force_authenticate(request, self.admin)
        self.assertEqual(UserViewSet.as_view({"get": "get_private_upload_token"})(request).status_code, 403)

    def test_all_locales_render_translated_rights_pages(self):
        for lang in ("ru", "en", "uk", "be", "kk"):
            with override(lang):
                for route in ("app_rights", "app_rights_add"):
                    response = self.client.get(reverse(route, kwargs={"pk": self.app.pk}))
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, "PAGE_ADMIN_APP_RIGHTS_")
                    self.assertNotContains(response, "FORM_APP_RIGHTS_")

    def test_private_application_and_distributions_v1_v2(self):
        from apps.api.views import MarketplaceViewSet, DistributionViewSet
        from apps.api.v2.views import MarketplaceViewSet as MarketplaceV2, DistributionViewSet as DistributionV2
        self.app.is_private = True
        self.app.save()
        for user in (self.owner, self.admin, self.editor, self.other, AnonymousUser()):
            allowed = user in (self.owner, self.admin, self.editor)
            for viewset, action, data, kwargs in (
                (MarketplaceViewSet, "get_app", {"id": self.app.pk}, {}),
                (DistributionViewSet, "get_distributions_list", {"id": self.app.pk}, {}),
                (MarketplaceV2, "retrieve", {}, {"pk": self.app.pk}),
                (DistributionV2, "retrieve", {}, {"pk": self.dist.pk}),
                (DistributionV2, "by_app", {"app_id": self.app.pk}, {}),
            ):
                with self.subTest(user=user, viewset=viewset, action=action):
                    request = APIRequestFactory().get("/resource", data)
                    force_authenticate(request, user)
                    response = viewset.as_view({"get": action})(request, **kwargs)
                    self.assertEqual(response.status_code == 200, allowed)

    def test_private_app_files_and_web_pages(self):
        self.app.is_private = True
        self.app.save()
        for user, allowed in ((self.owner, True), (self.admin, True), (self.editor, True), (self.other, False)):
            self.client.force_login(user)
            for url in (
                reverse("app") + f"?id={self.app.pk}",
                reverse("download") + f"?id={self.app.pk}",
                reverse("download_action", kwargs={"dist_pk": self.dist.pk}),
            ):
                with self.subTest(user=user, url=url):
                    self.assertEqual(self.client.get(url).status_code in (200, 302), allowed)

    def test_admin_can_change_privacy_but_not_community_mode(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("edit_app_info", kwargs={"pk": self.app.pk}), self.edit_data(
            is_private="on", allow_reviews="", allow_community_distributions="on",
        ))
        self.assertEqual(response.status_code, 302)
        req = AppEditRequests.objects.get(target_application=self.app)
        self.assertEqual(req.request_origin, "admin")
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_app_edit_request(req, actor=self.owner))
        self.app.refresh_from_db()
        self.assertTrue(self.app.is_private)
        self.assertFalse(self.app.allow_reviews)
        self.assertFalse(self.app.allow_community_distributions)
        self.assertEqual(self.client.get(reverse("community_access", kwargs={"pk": self.app.pk})).status_code, 403)

    def test_admin_approval_preserves_newer_review_setting(self):
        url = reverse("edit_app_info", kwargs={"pk": self.app.pk})
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, self.edit_data(allow_reviews="")).status_code, 302)
        req = AppEditRequests.objects.get(target_application=self.app)
        self.app.refresh_from_db()
        self.assertFalse(self.app.allow_reviews)

        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, self.edit_data(allow_reviews="on")).status_code, 302)
        self.app.refresh_from_db()
        self.assertTrue(self.app.allow_reviews)
        with patch("apps.marketplace.services.moderation.send_notification"):
            self.assertIsNotNone(approve_app_edit_request(req, actor=self.owner))
        self.app.refresh_from_db()
        self.assertTrue(self.app.allow_reviews)

    def test_revocation_during_form_validation_prevents_save(self):
        from apps.marketplace.forms import DelegatedAppEditForm
        original_clean = DelegatedAppEditForm.clean

        def revoke_during_validation(form):
            result = original_clean(form)
            set_application_access(self.app.pk, self.owner, self.admin, "none")
            return result

        self.client.force_login(self.admin)
        with patch.object(DelegatedAppEditForm, "clean", revoke_during_validation):
            response = self.client.post(reverse("edit_app_info", kwargs={"pk": self.app.pk}), self.edit_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AppEditRequests.objects.filter(target_application=self.app).exists())

    def test_downgrade_during_form_validation_prevents_admin_field_submission(self):
        from apps.marketplace.forms import DelegatedAppEditForm
        original_clean = DelegatedAppEditForm.clean

        def downgrade_during_validation(form):
            result = original_clean(form)
            set_application_access(self.app.pk, self.owner, self.admin, "editor")
            return result

        self.client.force_login(self.admin)
        with patch.object(DelegatedAppEditForm, "clean", downgrade_during_validation):
            response = self.client.post(reverse("edit_app_info", kwargs={"pk": self.app.pk}), self.edit_data(is_private="on"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AppEditRequests.objects.filter(target_application=self.app).exists())

    def test_revoked_signed_upload_cannot_create_release(self):
        import jwt
        from django.conf import settings

        self.client.force_login(self.admin)
        token_response = self.client.get(reverse("user-get-private-upload-token"), {"app_id": self.app.pk})
        claims = jwt.decode(token_response.json()["upload_token"], settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
        confirmation = jwt.encode({
            "type": "cdn-confirm", "file_id": 123, "guard": claims["guard"], "exp": claims["exp"],
        }, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256")

        def revoke_during_cdn_validation(*args, **kwargs):
            set_application_access(self.app.pk, self.owner, self.admin, "none")
            return {"hash": "test-hash"}

        with patch("apps.core.mixins.CDNTokenValidationMixin.get_cdn_file_info", side_effect=revoke_during_cdn_validation):
            response = self.client.post(reverse("manage_distributions") + f"?id={self.app.pk}", {
                "version": "2.0", "lunabox_type": "file", "cdn_confirm_token": confirmation,
                "virustotal_url": "https://www.virustotal.com/gui/file/test-hash",
            })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(DistributionCreateRequests.objects.filter(app=self.app).exists())

    def test_private_team_apps_do_not_appear_in_public_api_lists(self):
        from apps.api.v2.views import MarketplaceViewSet

        self.app.is_private = True
        self.app.save()
        for user in (self.owner, self.admin, self.editor):
            request = APIRequestFactory().get("/v2/marketplace/")
            force_authenticate(request, user)
            response = MarketplaceViewSet.as_view({"get": "list"})(request)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.app.pk, [row["id"] for row in response.data["results"]])

    def test_role_changes_notify_the_recipient_after_commit(self):
        transitions = (
            ("none", "admin", "GRANTED", "GRANTED_ADMIN"),
            ("none", "editor", "GRANTED", "GRANTED_EDITOR"),
            ("editor", "admin", "PROMOTED", "PROMOTED"),
            ("admin", "editor", "DEMOTED", "DEMOTED"),
            ("admin", "none", "REVOKED", "REVOKED"),
            ("editor", "none", "REVOKED", "REVOKED"),
        )
        for previous, role, event, description in transitions:
            with self.subTest(previous=previous, role=role):
                ApplicationAccess.objects.filter(application=self.app, user=self.other).delete()
                if previous != "none":
                    ApplicationAccess.objects.create(application=self.app, user=self.other, role=previous)
                with patch("apps.marketplace.services.access.send_notification") as notification_task:
                    enqueue = notification_task.enqueue
                    with self.captureOnCommitCallbacks(execute=True):
                        set_application_access(self.app.pk, self.owner, self.other, role)
                        enqueue.assert_not_called()
                    enqueue.assert_called_once_with(
                        user_id=self.other.pk, title_key=f"NOTIF_APP_ACCESS_{event}_TITLE",
                        content_key=f"NOTIF_APP_ACCESS_{description}_DESCRIPTION",
                        context={"app_name": self.app.title},
                        meta={"type": "info", "app_id": self.app.pk, "role": role, "previous_role": previous},
                    )

    def test_unchanged_roles_do_not_send_notifications(self):
        with patch("apps.marketplace.services.access.send_notification") as notification_task:
            enqueue = notification_task.enqueue
            with self.captureOnCommitCallbacks(execute=True):
                set_application_access(self.app.pk, self.owner, self.admin, "admin")
                set_application_access(self.app.pk, self.owner, self.editor, "editor")
                set_application_access(self.app.pk, self.owner, self.other, "none")
            enqueue.assert_not_called()

    def test_rolled_back_changes_do_not_send_notifications(self):
        with patch("apps.marketplace.services.access.send_notification") as notification_task:
            enqueue = notification_task.enqueue
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError), transaction.atomic():
                    set_application_access(self.app.pk, self.owner, self.other, "admin")
                    raise RuntimeError("Abort role change")
            enqueue.assert_not_called()
        self.assertFalse(ApplicationAccess.objects.filter(application=self.app, user=self.other).exists())

    def test_notification_escapes_application_title_and_is_localized_in_worker(self):
        from apps.core.tasks import send_notification

        self.app.title = '<img src=x onerror="alert(1)">'
        self.app.save()
        with patch("apps.marketplace.services.access.send_notification") as notification_task:
            enqueue = notification_task.enqueue
            with self.captureOnCommitCallbacks(execute=True):
                set_application_access(self.app.pk, self.owner, self.other, "editor")
        payload = enqueue.call_args.kwargs
        self.assertNotIn("<img", payload["context"]["app_name"])
        self.assertIn("&lt;img", payload["context"]["app_name"])
        for language in ("ru", "en", "uk", "be", "kk"):
            self.other.language = language
            with self.subTest(language=language), patch(
                "apps.core.tasks.User.objects.get", return_value=self.other,
            ), patch("apps.core.tasks.NotificationService.send_notification") as deliver:
                send_notification.call(**payload)
                message = deliver.call_args.kwargs
                self.assertEqual(message["user_id"], self.other.pk)
                self.assertNotIn("NOTIF_APP_ACCESS_", message["title"])
                self.assertNotIn("NOTIF_APP_ACCESS_", message["content"])
                self.assertNotIn("%(app_name)s", message["content"])
                self.assertIn("&lt;img", message["content"])


@override_settings(TELEGRAM_LOGGER_ENABLED=False, MEILISEARCH_ENABLED=False)
class ConcurrentApplicationAccessTests(TransactionTestCase):
    @patch("apps.marketplace.services.access.send_notification")
    def test_revocation_and_approval_serialize_on_application(self, enqueue):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        owner = User.objects.create(username="lock_owner", email="lock_owner@example.test")
        admin = User.objects.create(username="lock_admin", email="lock_admin@example.test")
        app = Application.objects.create(user=owner, title="Original")
        ApplicationAccess.objects.create(application=app, user=admin, role="admin", granted_by=owner)
        req = AppEditRequests.objects.create(
            target_application=app, user=admin, request_origin="admin", title="Forbidden update",
        )
        started = Event()

        def approve_in_other_connection():
            try:
                started.set()
                return approve_app_edit_request(req, actor=owner)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Application.objects.select_for_update().get(pk=app.pk)
                set_application_access(app.pk, owner, admin, "none")
                future = pool.submit(approve_in_other_connection)
                self.assertTrue(started.wait(timeout=5))
                self.assertFalse(future.done())
            self.assertIsNone(future.result(timeout=10))
        app.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(app.title, "Original")
        self.assertEqual(req.status, "rejected")
