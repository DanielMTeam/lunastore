from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext, override

from apps.core.themes import resolve_theme
from apps.core.views import theme_switch
from apps.user.forms import ThemePreferenceForm
from apps.user.models import User
from apps.user.views import settings_ui


class ThemeResolutionTests(SimpleTestCase):
    def test_account_preference_wins_over_cookie(self):
        for theme in ("classic_light", "classic_dark", "windows7"):
            request = RequestFactory().get("/", HTTP_COOKIE="dark_theme=on")
            request.user = SimpleNamespace(is_authenticated=True, theme=theme)
            self.assertEqual(resolve_theme(request), theme)

    def test_legacy_cookie_and_default(self):
        for authenticated in (True, False):
            for cookie, expected in (("on", "classic_dark"), ("off", "classic_light"), ("", "classic_light")):
                request = RequestFactory().get("/", HTTP_COOKIE="dark_theme=" + cookie)
                request.user = SimpleNamespace(is_authenticated=authenticated, theme=None)
                self.assertEqual(resolve_theme(request), expected)

    def test_unknown_stored_value_uses_legacy_fallback(self):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True, theme="unknown")
        self.assertEqual(resolve_theme(request), "classic_light")

    def test_classic_themes_need_no_javascript(self):
        for theme in ("classic_light", "classic_dark"):
            self.assertTrue(ThemePreferenceForm({"theme": theme}).is_valid())

    def test_windows7_requires_capability_for_new_selection(self):
        self.assertFalse(ThemePreferenceForm({"theme": "windows7"}).is_valid())
        self.assertTrue(ThemePreferenceForm({"theme": "windows7", "windows7_supported": "1"}).is_valid())

    def test_windows7_is_preserved_without_capability(self):
        form = ThemePreferenceForm({"theme": "windows7"}, current_theme="windows7")
        self.assertTrue(form.is_valid())

    def test_unknown_and_missing_values_are_rejected(self):
        for data in ({}, {"theme": "invalid"}):
            self.assertFalse(ThemePreferenceForm(data).is_valid())

    def test_retired_switch_never_sets_cookies(self):
        for payload in ("on", "off"):
            request = RequestFactory().get("/theme_switch.php", {"payload": payload, "next": "https://example.com"})
            response = theme_switch(request)
            self.assertEqual(response.url, reverse("settings_ui"))
            self.assertFalse(response.cookies)

    def test_settings_require_login(self):
        for method in ("get", "post"):
            request = getattr(RequestFactory(), method)(reverse("settings_ui"))
            request.user = AnonymousUser()
            with override_settings(ALLOWED_HOSTS=["testserver"]):
                response = settings_ui(request)
            self.assertEqual(response.status_code, 302)
            self.assertIn("next=", response.url)

    def test_theme_strings_are_translated_in_all_site_languages(self):
        for language in ("ru", "en", "uk", "be", "kk"):
            with override(language):
                for key in ("THEME_CLASSIC_LIGHT", "THEME_CLASSIC_DARK", "PAGE_SETTINGS_THEME_TITLE",
                            "ERROR_THEME_UNSUPPORTED", "INFO_THEME_FALLBACK", "INFO_THEME_UPDATED"):
                    self.assertNotEqual(gettext(key), key)

    def test_post_is_csrf_protected(self):
        request = RequestFactory().post(reverse("settings_ui"), {"action": "theme", "theme": "classic_dark"})
        response = CsrfViewMiddleware(lambda r: HttpResponse()).process_view(request, settings_ui, (), {})
        self.assertEqual(response.status_code, 403)


@override_settings(CONSTANCE_BACKEND="constance.backends.memory.MemoryBackend")
class ThemePersistenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="themeuser", email="theme@example.com")

    def request(self, method="post", data=None, **headers):
        request = getattr(RequestFactory(), method)(reverse("settings_ui"), data or {}, **headers)
        request.user = User.objects.get(pk=self.user.pk)
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_saves_only_theme_and_resolves_on_another_device(self):
        for theme in ("classic_light", "classic_dark", "windows7"):
            request = self.request(data={"action": "theme", "theme": theme, "windows7_supported": "1"})
            self.assertEqual(settings_ui(request).status_code, 302)
            self.user.refresh_from_db()
            self.assertEqual(self.user.theme, theme)
            self.assertEqual(self.user.home_layout, "rich")
            another_device = self.request("get", HTTP_COOKIE="dark_theme=on", HTTP_USER_AGENT="MSIE 6.0")
            self.assertEqual(resolve_theme(another_device), theme)

    def test_invalid_theme_or_missing_capability_does_not_save(self):
        for data in ({"theme": "unknown"}, {"theme": "windows7"}, {}):
            settings_ui(self.request(data={"action": "theme", **data}))
            self.user.refresh_from_db()
            self.assertIsNone(self.user.theme)

    def test_existing_windows7_survives_unsupported_post(self):
        self.user.theme = "windows7"
        self.user.save(update_fields=["theme"])
        settings_ui(self.request(data={"action": "theme", "theme": "windows7"}))
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "windows7")

    def test_layout_form_does_not_change_theme(self):
        self.user.theme = "windows7"
        self.user.save(update_fields=["theme"])
        settings_ui(self.request(data={"home_view": "compact"}))
        self.user.refresh_from_db()
        self.assertEqual(self.user.home_layout, "compact")
        self.assertEqual(self.user.theme, "windows7")

    def test_get_does_not_save_theme(self):
        with patch("apps.user.views.render", return_value=HttpResponse()):
            settings_ui(self.request("get", {"action": "theme", "theme": "classic_dark"}))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.theme)

    def test_settings_markup_keeps_forms_independent_and_windows7_disabled(self):
        response = settings_ui(self.request("get"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="theme-settings"', html)
        self.assertIn('id="theme-windows7" disabled', html)
        self.assertIn('name="home_view"', html)
        self.assertNotIn('href="/theme_switch.php', html)

    def test_windows7_markup_has_no_unconditional_stylesheet(self):
        self.user.theme = "windows7"
        self.user.save(update_fields=["theme"])
        response = settings_ui(self.request("get", HTTP_USER_AGENT="MSIE 6.0"))
        html = response.content.decode()
        self.assertNotIn('id="windows7-css"', html)
        self.assertNotIn('id="darkthm-css"', html)
        self.assertIn('id="theme-fallback"', html)
        self.assertIn('name="theme" value="windows7"', html)

    def test_classic_dark_stylesheet_comes_from_registry(self):
        self.user.theme = "classic_dark"
        self.user.save(update_fields=["theme"])
        html = settings_ui(self.request("get")).content.decode()
        self.assertIn('id="darkthm-css" href="/staticfiles/css/darkthm.css"', html)
        self.assertNotIn('id="windows7-css"', html)
