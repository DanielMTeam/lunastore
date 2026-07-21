from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import Permission
from apps.user.models import NoSpamRule, User, UserActivityLog, UserBan
from apps.user.services.antispam import AntiSpamService, NoSpamContext
from apps.user.forms import NoSpamMassScanForm
from rest_framework.test import APIClient
import logging

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
        resp = self.client.get('/logout.php')
        self.assertEqual(resp.status_code, 302)

    def test_logout_url_by_name(self):
        logger.info('[User APP; Logout PAGE] Testing URL by name...')
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 302)


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

    def test_parse_user_id_range_invalid_returns_none(self):
        self.assertIsNone(AntiSpamService._parse_user_id_range("not-a-range"))

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
