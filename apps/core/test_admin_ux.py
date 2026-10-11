from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import resolve, reverse
from django.utils.translation import gettext, override
from django.views.i18n import set_language

from apps.core.dashboard import callback, queue_badge
from apps.marketplace.admin import ReviewAdmin
from apps.marketplace.admin_comparison import comparison_rows
from apps.marketplace.models import AppCreateRequests, PendingReview, Review


@override_settings(ROOT_URLCONF="lunastore.urls_private")
class AdminUXTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, url):
        request = self.factory.get(url)
        request.resolver_match = resolve(request.path)
        request.user = Mock(is_active=True, is_staff=True, is_superuser=True)
        request.user.has_perm.return_value = True
        return request

    def test_sidebar_has_one_active_link_on_list_detail_and_history(self):
        for model in ("review", "pendingreview", "application", "appeditrequests"):
            for action, args in (("changelist", None), ("change", [1]), ("history", [1])):
                with self.subTest(model=model, action=action):
                    request = self.request(reverse(f"admin:marketplace_{model}_{action}", args=args))
                    navigation = admin.site.get_sidebar_list(request)
                    active = [item for group in navigation for item in group["items"] if item["active"]]
                    self.assertEqual(len(active), 1)
                    self.assertEqual(str(active[0]["link"]), reverse(f"admin:marketplace_{model}_changelist"))

    def test_custom_pages_have_one_active_link(self):
        for name in ("admin:index", "broadcast", "admin_nospam_mass_scan"):
            request = self.request(reverse(name))
            active = [item for group in admin.site.get_sidebar_list(request)
                      for item in group["items"] if item["active"]]
            self.assertEqual(len(active), 1)

    def test_language_switch_keeps_admin_url_and_localizes_components(self):
        expected = {"ru": "Рабочий стол", "en": "Dashboard", "uk": "Робочий стіл",
                    "be": "Працоўны стол", "kk": "Жұмыс үстелі"}
        url = reverse("admin:marketplace_review_changelist") + "?rating__exact=5"
        for language, label in expected.items():
            request = self.factory.post(reverse("set_language"), {"language": language, "next": url})
            response = set_language(request)
            self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, language)
            self.assertEqual(response.url, url)
            with override(language):
                self.assertEqual(gettext("PAGE_ADMIN_PANEL_DASHBOARD"), label)

    def test_review_form_labels_use_named_keys_in_all_languages(self):
        model_admin = ReviewAdmin(Review, admin.site)
        request = self.request(reverse("admin:marketplace_review_changelist"))
        expected = {"ru": "Заметка модератора", "en": "Moderator note", "uk": "Нотатка модератора",
                    "be": "Нататка мадэратара", "kk": "Модератор жазбасы"}
        for language, label in expected.items():
            with self.subTest(language=language), override(language):
                field = model_admin.formfield_for_dbfield(Review._meta.get_field("moderation_note"), request)
                self.assertEqual(str(field.label), label)
                message = gettext("PAGE_ADMIN_PANEL_REVIEWS_APPROVED_MESSAGE %(count)s") % {"count": 3}
                self.assertIn("3", message)
                self.assertNotIn("PAGE_ADMIN_PANEL_", message)

    def test_dashboard_without_permissions_does_not_query_or_disclose_data(self):
        request = self.request(reverse("admin:index"))
        request.user.has_perm.return_value = False
        result = callback(request, {})
        self.assertEqual(result["moderation_queues"], [])
        self.assertEqual(result["statistics"], [])
        self.assertEqual(result["pending_total"], 0)

    def test_dashboard_uses_pending_visible_queue_and_oldest_item(self):
        request = self.request(reverse("admin:index"))
        request.user.has_perm.side_effect = lambda permission: permission == "marketplace.view_appcreaterequests"
        queryset = Mock()
        queryset.filter.return_value = queryset
        queryset.aggregate.return_value = {"total": 3, "oldest": None}
        queryset.order_by.return_value.first.return_value = SimpleNamespace(pk=7, title="Old request", created_at=None)
        with patch.object(admin.site._registry[AppCreateRequests], "get_queryset", return_value=queryset):
            result = callback(request, {})
        self.assertEqual(result["pending_total"], 3)
        self.assertEqual(len(result["moderation_queues"]), 1)
        self.assertIn("status__exact=pending", result["moderation_queues"][0]["url"])
        queryset.filter.assert_any_call(status="pending")
        queryset.filter.assert_any_call(deleted__isnull=True)
        self.assertEqual(result["oldest_requests"][0]["preview"], "Old request")

    def test_queue_badges_reuse_counts_and_hide_unauthorized_data(self):
        request = self.request(reverse("admin:index"))
        request._luna_queue_counts = {AppCreateRequests: 3}
        self.assertEqual(queue_badge(request, AppCreateRequests), "3")
        request.user.has_perm.return_value = False
        self.assertEqual(queue_badge(request, AppCreateRequests), "")

    def test_sidebar_uses_change_and_proxy_permissions(self):
        request = self.request(reverse("admin:index"))
        request.user.has_perm.side_effect = lambda permission: permission in (
            "marketplace.change_application", "marketplace.view_pendingreview",
        )
        items = {str(item["link"]): item for group in admin.site.get_sidebar_list(request) for item in group["items"]}
        self.assertTrue(items[reverse("admin:marketplace_application_changelist")]["has_permission"])
        self.assertTrue(items[reverse("admin:marketplace_pendingreview_changelist")]["has_permission"])
        self.assertFalse(items[reverse("admin:marketplace_review_changelist")]["has_permission"])

    def test_review_text_and_flags_are_escaped(self):
        model_admin = ReviewAdmin(Review, admin.site)
        obj = SimpleNamespace(text='<script>alert("x")</script>', ai_score=0.5, ai_flags=['<img src=x onerror=alert(1)>'])
        self.assertNotIn("<script>", model_admin.text_preview(obj))
        self.assertIn("&lt;script&gt;", model_admin.text_preview(obj))
        self.assertNotIn("<img", model_admin.ai_flags_display(obj))
        obj.ai_score = None
        obj.ai_flags = []
        with override("en"):
            self.assertIn("Not scored", model_admin.ai_score_badge(obj))
            self.assertIn("Not scored", model_admin.ai_flags_display(obj))

    def test_review_filters_preserve_search_and_reset_page(self):
        model_admin = ReviewAdmin(Review, admin.site)
        request = self.request(reverse("admin:marketplace_review_changelist") + "?q=XP&p=3&rating__exact=5")
        with patch("unfold.admin.ModelAdmin.changelist_view") as view:
            model_admin.changelist_view(request)
        links = view.call_args.kwargs["extra_context"]["review_status_links"]
        for item in links:
            self.assertIn("q=XP", item["url"])
            self.assertIn("rating__exact=5", item["url"])
            self.assertNotIn("p=3", item["url"])

    def test_comparison_respects_retained_file_and_shows_translation_changes(self):
        target = SimpleNamespace(version="1.0", url="https://example.com/old", lunabox_manifest={}, cdn_file_id=17)
        obj = SimpleNamespace(target_distribution=target, version="2.0", url=target.url,
                              lunabox_manifest={}, cdn_file_id=None)
        for code, _label in settings.LANGUAGES:
            setattr(target, f"changelog_{code}", "old")
            setattr(obj, f"changelog_{code}", "old")
        obj.changelog_en = '<script>alert("x")</script>'
        with override("en"):
            rows = comparison_rows(obj)
            self.assertEqual([row["label"] for row in rows], ["Version", "Changelog (en)"])
            html = render_to_string("admin/decline_forms/comparison.html",
                                    {"request_comparison": rows, "original": {"status": "pending"}})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_comparison_is_absent_on_other_request_forms(self):
        html = render_to_string("admin/decline_forms/comparison.html", {})
        self.assertNotIn("luna-comparison", html)
