from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import Permission
from apps.user.models import NoSpamRule, User, UserActivityLog, UserBan
from apps.user.services.antispam import AntiSpamService, NoSpamContext
from apps.user.forms import NoSpamMassScanForm
from rest_framework.test import APIClient
import logging
import os
import tempfile
from unittest import mock

logger = logging.getLogger('user')


class UserModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[User APP; User MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
            username='TestUser',
            password='TestPassword',
            first_name='TestFirstName',
            last_name='TestLastName',
            email='fayzetwin.xd@gmail.com',
            telegram='@TestTelegram',
            discord='TestDiscord#1234',
            website='https://fayzetwin.xyz',
            description='This is a test user'
        )

    def test_username_content(self):
        logger.info('[User APP; User MODEL] Testing "username" field...')
        obj = User.objects.get(id=self.user.id)
        self.assertEqual(obj.username, 'TestUser')


class UserBanModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info('[User APP; UserBan MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
            username='BannedUser',
            password='BannedPassword'
        )
        cls.userban = UserBan.objects.create(
            user=cls.user,
            ip='127.0.0.1',
            reason='Test reason for ban'
        )

    def test_ban_reason_content(self):
        logger.info('[User APP; UserBan MODEL] Testing "reason" field...')
        obj = UserBan.objects.get(id=self.userban.id)
        self.assertEqual(obj.reason, 'Test reason for ban')


class UserActivityModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info(
            '[User APP; UserActivityLog MODEL] Creating test data in DB...')
        cls.user = User.objects.create(
            username='ActiveUser',
            password='ActivePassword'
        )
        cls.useractivity = UserActivityLog.objects.create(
            user=cls.user,
            ip='127.0.0.1',
            action='Logged In'
        )

    def test_activity_action_content(self):
        logger.info(
            '[User APP; UserActivityLog MODEL] Testing "action" field...')
        obj = UserActivityLog.objects.get(id=self.useractivity.id)
        self.assertEqual(obj.action, 'Logged In')


class AuthPagesTest(TestCase):
    def test_logout_url_by_path(self):
        logger.info('[User APP; Logout PAGE] Testing URL by direct path...')
        resp = self.client.post('/logout.php')
        self.assertEqual(resp.status_code, 302)

    def test_logout_url_by_name(self):
        logger.info('[User APP; Logout PAGE] Testing URL by name...')
        resp = self.client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 302)

    def test_logout_rejects_get(self):
        logger.info('[User APP; Logout PAGE] Testing GET is rejected...')
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 405)


@override_settings(CONSTANCE_BACKEND="constance.backends.memory.MemoryBackend")
class NoSpamServiceTest(TestCase):
    def setUp(self):
        from constance import config
        config.NOSPAM_ENABLED = True
        config.NOSPAM_CACHE_TTL = 1
        config.NOSPAM_SHIELD_ENABLED = False
        self.user = User.objects.create_user(
            username="nospam_user",
            password="StrongPassword123!",
            email="nospam@example.com",
        )

    def test_email_domain_rule_bans_user(self):
        NoSpamRule.objects.create(
            name="ban-example-domain",
            entrypoints="register,jwt_token",
            action=NoSpamRule.RuleAction.BAN,
            match_type=NoSpamRule.MatchType.EMAIL_DOMAIN,
            pattern="example.com",
            reason_template="blocked domain",
            ban_by_ip=True,
            is_permanent=False,
            ban_duration_minutes=30,
        )

        decision = AntiSpamService.evaluate_and_apply(
            context=NoSpamContext(
                entrypoint="jwt_token",
                ip="127.0.0.1",
                email=self.user.email,
                username=self.user.username,
                user_agent="pytest-agent",
                user=self.user,
            ),
            target_user=self.user,
        )
        self.user.refresh_from_db()

        self.assertTrue(decision.should_block)
        self.assertEqual(decision.action, NoSpamRule.RuleAction.BAN)
        self.assertFalse(self.user.is_active)
        self.assertTrue(UserBan.objects.filter(user=self.user).exists())

    def test_request_rate_signal_blocks(self):
        NoSpamRule.objects.create(
            name="rate-signal",
            entrypoints="login",
            action=NoSpamRule.RuleAction.BAN,
            match_type=NoSpamRule.MatchType.REQUEST_RATE_SIGNAL,
            payload={"max_hits": 2, "window_seconds": 60},
            reason_template="too many requests",
        )
        first = AntiSpamService.evaluate(
            NoSpamContext(entrypoint="login", ip="10.0.0.2"))
        second = AntiSpamService.evaluate(
            NoSpamContext(entrypoint="login", ip="10.0.0.2"))

        self.assertFalse(first.should_block)
        self.assertTrue(second.should_block)

    def test_user_id_range_filter(self):
        target_user = User.objects.create_user(
            username="range_user",
            password="StrongPassword123!",
            email="range@example.com",
        )
        users_qs, matched_label = AntiSpamService.find_users_by_filter(
            match_type=NoSpamRule.MatchType.USER_ID_RANGE,
            pattern=f"{target_user.id - 1}:{target_user.id + 1}",
        )
        self.assertIn(target_user.id, list(users_qs.values_list("id", flat=True)))
        self.assertIn(":", matched_label)


@override_settings(CONSTANCE_BACKEND="constance.backends.memory.MemoryBackend")
class JwtNoSpamIntegrationTest(TestCase):
    def setUp(self):
        from constance import config
        config.NOSPAM_ENABLED = True
        config.NOSPAM_CACHE_TTL = 1
        config.NOSPAM_SHIELD_ENABLED = False
        self.user = User.objects.create_user(
            username="jwt_nospam",
            password="StrongPassword123!",
            email="jwt@example.com",
        )
        self.client = APIClient()

    def test_jwt_token_blocked_by_nospam_rule(self):
        NoSpamRule.objects.create(
            name="jwt-block-rule",
            entrypoints="jwt_token",
            action=NoSpamRule.RuleAction.BAN,
            match_type=NoSpamRule.MatchType.USERNAME_REGEX,
            pattern="jwt_.*",
            reason_template="jwt blocked",
        )

        response = self.client.post(
            "/method/v2/auth/token/",
            {"username": "jwt_nospam", "password": "StrongPassword123!"},
            format="json",
        )
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.user.is_active)


class NoSpamSecurityTest(TestCase):
    def test_mass_scan_form_requires_confirm_for_ban(self):
        form = NoSpamMassScanForm(
            data={
                "match_type": NoSpamRule.MatchType.EMAIL_DOMAIN,
                "pattern": "example.com",
                "action": NoSpamRule.RuleAction.BAN,
                "reason": "test ban",
                "confirm": False,
            },
            scan_step="apply",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("подтверждение", str(form.errors).lower())

    def test_mass_scan_form_allows_log_without_confirm(self):
        form = NoSpamMassScanForm(
            data={
                "match_type": NoSpamRule.MatchType.EMAIL_DOMAIN,
                "pattern": "example.com",
                "action": NoSpamRule.RuleAction.LOG,
                "reason": "test log",
                "confirm": False,
            },
            scan_step="apply",
        )
        self.assertTrue(form.is_valid())

    def test_parse_user_id_range_swaps_bounds(self):
        parsed = AntiSpamService._parse_user_id_range("500:100")
        self.assertEqual(parsed, (100, 500))

    def test_parse_user_id_range_invalid_raises(self):
        with self.assertRaises(ValueError):
            AntiSpamService._parse_user_id_range("not-a-range")

    def test_safe_regex_invalid_pattern_returns_false(self):
        self.assertFalse(AntiSpamService._safe_regex_match("[invalid", "value"))

    def test_mass_scan_permissions(self):
        viewer = User.objects.create_user(
            username="nospam_viewer",
            password="StrongPassword123!",
            email="viewer@example.com",
            is_staff=True,
        )
        view_perm = Permission.objects.get(
            codename="view_nospamrule",
            content_type__app_label="user",
        )
        viewer.user_permissions.add(view_perm)

        self.assertTrue(viewer.has_perm("user.view_nospamrule"))
        self.assertFalse(viewer.has_perm("user.add_userban"))
        self.assertFalse(viewer.has_perm("user.delete_user"))

        from apps.user.admin_views import _has_mass_action_permission
        self.assertTrue(
            _has_mass_action_permission(viewer, NoSpamRule.RuleAction.LOG)
        )
        self.assertFalse(
            _has_mass_action_permission(viewer, NoSpamRule.RuleAction.BAN)
        )
        self.assertFalse(
            _has_mass_action_permission(viewer, NoSpamRule.RuleAction.DELETE)
        )


@override_settings(CONSTANCE_BACKEND="constance.backends.memory.MemoryBackend")
class NoSpamMassActionTest(TestCase):
    def setUp(self):
        from constance import config
        config.NOSPAM_ENABLED = True
        self.user = User.objects.create_user(
            username="mass_log_user",
            password="StrongPassword123!",
            email="mass@example.com",
        )

    def test_apply_mass_action_log_creates_event(self):
        stats = AntiSpamService.apply_mass_action(
            users=[self.user],
            action=NoSpamRule.RuleAction.LOG,
            reason="security test log",
            matched_value="mass@example.com",
        )
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["logged"], 1)
        self.assertEqual(stats["banned"], 0)
        self.assertEqual(stats["deleted"], 0)
        from apps.user.models import NoSpamEvent
        self.assertTrue(
            NoSpamEvent.objects.filter(
                user=self.user,
                entrypoint="admin_mass_scan",
                action=NoSpamRule.RuleAction.LOG,
            ).exists()
        )

    def test_apply_mass_action_ban_creates_event(self):
        stats = AntiSpamService.apply_mass_action(
            users=[self.user],
            action=NoSpamRule.RuleAction.BAN,
            reason="security test ban",
            matched_value="mass@example.com",
        )
        self.assertEqual(stats["banned"], 1)
        from apps.user.models import NoSpamEvent
        self.assertTrue(
            NoSpamEvent.objects.filter(
                user=self.user,
                entrypoint="admin_mass_scan",
                action=NoSpamRule.RuleAction.BAN,
            ).exists()
        )


class LunaPassportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="passport_user",
            email="passport_user@example.com",
            password="TestPassword123!",
        )

    def test_passport_endpoints_404_when_disabled(self):
        resp = self.client.get(reverse("passport_login"))
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(reverse("passport_callback"))
        self.assertEqual(resp.status_code, 404)

    def test_passport_link_model(self):
        from apps.user.models import LunaPassportLink
        link = LunaPassportLink.objects.create(
            user=self.user,
            sub="passport_user@example.com",
            sign_in="passport_user@example.com",
            passport_name="Passport User",
        )
        self.assertEqual(self.user.passport_link.sub, link.sub)

    def test_unlink_requires_login(self):
        resp = self.client.post(reverse("passport_unlink"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login.php", resp.url)

    def test_sanitize_and_unique_username_helpers(self):
        from apps.user.views_passport import _sanitize_username, _unique_username
        self.assertEqual(_sanitize_username("Foo.Bar!"), "foo.bar")
        self.assertTrue(_unique_username("passport_user").startswith("passport_user"))

    def test_verify_defaults_to_true(self):
        from apps.user.services import lunapassport as passport
        self.assertTrue(passport.get_verify())

    def test_verify_false_from_env(self):
        from apps.user.services import lunapassport as passport
        with mock.patch.dict(os.environ, {"LUNAPASSPORT_VERIFY_SSL": "False"}):
            self.assertFalse(passport.get_verify())

    def test_verify_uses_ca_bundle(self):
        from apps.user.services import lunapassport as passport
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as fh:
            fh.write("-----BEGIN CERTIFICATE-----\n")
            bundle_path = fh.name
        try:
            with mock.patch.dict(os.environ, {"LUNAPASSPORT_CA_BUNDLE": bundle_path}):
                self.assertEqual(passport.get_verify(), bundle_path)
        finally:
            os.unlink(bundle_path)

    def test_verify_missing_ca_bundle_raises(self):
        from apps.user.services import lunapassport as passport
        with mock.patch.dict(os.environ, {"LUNAPASSPORT_CA_BUNDLE": "certs/missing.pem"}):
            with self.assertRaises(passport.LunaPassportError):
                passport.get_verify()

    def test_verify_invalid_ca_bundle_raises(self):
        from apps.user.services import lunapassport as passport
        with tempfile.NamedTemporaryFile("wb", suffix=".pem", delete=False) as fh:
            fh.write(b"not a pem certificate")
            bundle_path = fh.name
        try:
            with mock.patch.dict(os.environ, {"LUNAPASSPORT_CA_BUNDLE": bundle_path}):
                with self.assertRaises(passport.LunaPassportError):
                    passport.get_verify()
        finally:
            os.unlink(bundle_path)

    @mock.patch.dict(os.environ, {
        "LUNAPASSPORT_BASE_URL": "https://passport.internal",
        "LUNAPASSPORT_CLIENT_ID": "cid",
        "LUNAPASSPORT_CLIENT_SECRET": "secret",
        "LUNAPASSPORT_REDIRECT_URI": "http://localhost/passport/callback.php",
        "LUNAPASSPORT_VERIFY_SSL": "False",
    })
    @mock.patch("apps.user.services.lunapassport.build_http_session")
    def test_exchange_code_passes_verify(self, mock_session_factory):
        from apps.user.services import lunapassport as passport
        session = mock_session_factory.return_value
        session.__enter__.return_value = session
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {"access_token": "tok"}
        self.assertEqual(passport.exchange_code("abc"), "tok")
        self.assertFalse(session.post.call_args.kwargs["verify"])

    def test_build_tls_context_relaxes_x509_strict_only(self):
        import ssl

        import requests.certs
        from apps.user.services import lunapassport as passport
        context = passport.build_tls_context(requests.certs.where())
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_STRICT)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_build_http_session_mounts_tls_adapter_for_ca_bundle(self):
        import requests.certs
        from apps.user.services import lunapassport as passport
        session = passport.build_http_session(requests.certs.where())
        try:
            adapter = session.get_adapter("https://example.com")
            self.assertIsInstance(adapter, passport._PassportTLSAdapter)
        finally:
            session.close()


class AdminRedirectTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.regular_user = User.objects.create_user(
            username="regular_user",
            password="Password123!",
            email="regular@example.com",
        )
        cls.staff_user = User.objects.create_user(
            username="staff_user",
            password="Password123!",
            email="staff@example.com",
            is_staff=True,
        )

    def test_anonymous_user_404(self):
        response = self.client.get(reverse("admin_redirect"))
        self.assertEqual(response.status_code, 404)

        response_panel = self.client.get(reverse("admin_panel"))
        self.assertEqual(response_panel.status_code, 404)

    def test_regular_user_404(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("admin_redirect"))
        self.assertEqual(response.status_code, 404)

    def test_staff_user_redirect_default(self):
        self.client.force_login(self.staff_user)
        with override_settings(ADMIN_URL="admin"):
            response = self.client.get(reverse("admin_redirect"))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "http://testserver/admin/")

    def test_staff_user_redirect_port_switch(self):
        self.client.force_login(self.staff_user)
        with override_settings(ADMIN_URL="office"):
            response = self.client.get(reverse("admin_redirect"), HTTP_HOST="localhost:9088")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "http://localhost:8088/office/")

    def test_staff_user_redirect_full_url(self):
        self.client.force_login(self.staff_user)
        with override_settings(ADMIN_URL="https://admin.lunastore.app/secret"):
            response = self.client.get(reverse("admin_redirect"))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "https://admin.lunastore.app/secret/")

    def test_sidebar_admin_link_visibility(self):
        # Non-staff user should NOT see the admin link in sidebar
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("admin_redirect"))

        # Staff user SHOULD see the admin link in sidebar
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin_redirect"))


class UserSafeDeleteUniquenessTests(TestCase):
    def test_re_registration_after_soft_delete(self):
        user1 = User.objects.create_user(
            username="recycled_user",
            email="recycled@example.com",
            password="Password123!"
        )
        # Soft delete first user
        user1.delete()
        self.assertIsNotNone(user1.deleted)

        # Creating a second user with the same username and email should succeed
        user2 = User.objects.create_user(
            username="recycled_user",
            email="recycled@example.com",
            password="NewPassword123!"
        )
        self.assertEqual(user2.username, "recycled_user")
        self.assertEqual(user2.email, "recycled@example.com")
        self.assertIsNone(user2.deleted)

        # Both users exist in all_objects
        self.assertEqual(User.all_objects.filter(username="recycled_user").count(), 2)
        # Only 1 user exists in active objects
        self.assertEqual(User.objects.filter(username="recycled_user").count(), 1)

    def test_duplicate_active_user_raises_integrity_error(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user(
            username="active_user",
            email="active@example.com",
            password="Password123!"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    username="active_user",
                    email="different@example.com",
                    password="Password123!"
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    username="different_user",
                    email="active@example.com",
                    password="Password123!"
                )

    def test_blacklisted_username_recreation_after_soft_delete(self):
        from apps.user.models import BlacklistedUsername

        w1 = BlacklistedUsername.objects.create(word="badname")
        w1.delete()
        self.assertIsNotNone(w1.deleted)

        # Creating another active entry with same word should succeed
        w2 = BlacklistedUsername.objects.create(word="badname")
        self.assertIsNone(w2.deleted)
        self.assertEqual(BlacklistedUsername.objects.filter(word="badname").count(), 1)
        self.assertEqual(BlacklistedUsername.all_objects.filter(word="badname").count(), 2)
