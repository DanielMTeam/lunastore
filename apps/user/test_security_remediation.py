import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pyotp
from constance import config
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.db import close_old_connections, connections
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.api.authentication import CustomJWTAuthentication
from apps.api.token_sessions import issue_tokens, rotate_tokens
from apps.user.admin import UserAdmin
from apps.user.auth import OIDCModel
from apps.user.models import APISession, OIDCIdentity, User, UserBan
from apps.core.utils import get_ip_limit_key
from apps.user.services.bans import is_ip_banned
from apps.user.services.login_security import allow_password_attempt, verify_totp


class LoginSecurityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_password_limit_uses_normalized_account(self):
        request = RequestFactory().post("/login.php", REMOTE_ADDR="192.0.2.1")
        for _ in range(10):
            self.assertTrue(allow_password_attempt(request, "Alice"))
        self.assertFalse(allow_password_attempt(request, "ALICE"))

    @override_settings(TRUSTED_PROXIES=["127.0.0.1/32"])
    def test_untrusted_peer_cannot_spoof_rate_limit_key(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="203.0.113.5",
        )
        self.assertEqual(get_ip_limit_key(request), "unresolved:ip:192.0.2.1")

    def test_totp_is_single_use(self):
        user = SimpleNamespace(pk=1, totp_secret=pyotp.random_base32())
        with patch("apps.user.services.login_security.time.time", return_value=1_800_000_000):
            code = pyotp.TOTP(user.totp_secret).generate_otp(1_800_000_000 // 30)
            self.assertTrue(verify_totp(user, code))
            self.assertFalse(verify_totp(user, code))

    @override_settings(ROOT_URLCONF="lunastore.urls_private", ALLOWED_HOSTS=["localhost", "admin.lunastore.app"])
    def test_impersonation_redirects_from_dedicated_admin(self):
        actor = Mock(id=1, is_superuser=True)
        actor.get_session_auth_hash.return_value = "auth-hash"
        target = SimpleNamespace(is_active=True, is_staff=False, is_superuser=False)
        model_admin = UserAdmin(User, None)
        changelist = reverse("admin:user_user_changelist")
        for host, destination in (
            ("localhost:8088", "//localhost:9088/index.php"),
            ("admin.lunastore.app", "//lunastore.app/index.php"),
        ):
            with self.subTest(host=host):
                request = RequestFactory().post("/", HTTP_HOST=host)
                request.user = actor
                request.session = {"_auth_user_backend": "django.contrib.auth.backends.ModelBackend"}
                with patch.object(model_admin, "get_object", return_value=target), \
                        patch.object(model_admin, "log_change"), \
                        patch("apps.user.admin.active_bans") as bans, \
                        patch("django.contrib.auth.login") as login:
                    bans.return_value.filter.return_value.exists.return_value = False
                    response = model_admin.login_as_user(request, object_id="2")
                self.assertRedirects(response, destination, fetch_redirect_response=False)
                self.assertEqual(request.session["impersonated_by"], actor.id)
                self.assertEqual(request.session["impersonator_return_url"], f"//{host}{changelist}")
                login.assert_called_once()


class AccountSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.test", password="original-password",
        )

    def test_expired_ip_ban_and_profile_read_have_no_side_effects(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        ban = UserBan.objects.create(
            user=self.user, ip="192.0.2.1", ban_by_ip=True,
            expires_at=timezone.now() - timedelta(seconds=1), reason="test",
        )
        cache.set("banned_ips_list", {"192.0.2.1"}, timeout=60)
        self.assertFalse(is_ip_banned("192.0.2.1"))
        self.assertEqual(self.client.get(reverse("profile"), {"id": self.user.pk}).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(UserBan.objects.filter(pk=ban.pk).exists())

    def test_legacy_tokens_require_fresh_login(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        response = APIClient().post(
            "/method/v2/auth/token/refresh/", {"refresh": str(refresh)}, format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_post_cannot_change_credentials(self):
        self.client.force_login(self.user)
        self.client.post(reverse("settings"), {
            "form_type": "profile", "username": "alice", "email": "other@example.test",
        })
        self.client.post(reverse("settings"), {
            "form_type": "password", "current_password": "original-password",
            "new_password": "replacement-password", "confirm_password": "replacement-password",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.test")
        self.assertTrue(self.user.check_password("original-password"))

    def test_new_session_cannot_change_email(self):
        self.client.force_login(self.user)
        self.client.post(reverse("settings_security"), {
            "form_type": "email", "new_email": "other@example.test", "password_check": "original-password",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.test")

    @override_settings(ROOT_URLCONF="lunastore.urls_private", DEBUG=True, ALLOWED_HOSTS=["localhost", "testserver"])
    def test_impersonation_blocks_staff_target_and_get_return(self):
        actor = User.objects.create_superuser(username="admin", email="admin@example.test")
        staff = User.objects.create_user(username="staff", email="staff@example.test", is_staff=True)
        self.client.force_login(actor)
        url = reverse("admin:user_user_login_as_user", args=[staff.pk])
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(url, HTTP_HOST="localhost:8088")
                self.assertTemplateUsed(response, "admin/403.html")
                self.assertContains(response, "Вход от имени сотрудников и суперпользователей запрещён.", status_code=403)
                self.assertEqual(int(self.client.session["_auth_user_id"]), actor.pk)
        self.client.force_login(self.user)
        with self.settings(ROOT_URLCONF="lunastore.urls"):
            self.assertEqual(self.client.get(reverse("revert_impersonation")).status_code, 405)

    @override_settings(ROOT_URLCONF="lunastore.urls_private", TELEGRAM_LOGGER_ENABLED=False)
    def test_moderator_switch_allows_only_regular_target(self):
        moderator = User.objects.create_user(username="moderator", email="mod@example.test", is_staff=True)
        moderator.groups.add(Group.objects.get(name="Модераторы"))
        staff = User.objects.create_user(username="staff", email="staff@example.test", is_staff=True)
        self.client.force_login(moderator)
        regular_url = reverse("admin:user_user_login_as_user", args=[self.user.pk])
        staff_url = reverse("admin:user_user_login_as_user", args=[staff.pk])

        with patch("constance.config", wraps=config, ALLOW_MODERATOR_LOGIN_AS_USER=False):
            self.assertRedirects(
                self.client.get(regular_url), reverse("admin:user_user_change", args=[self.user.pk]),
                fetch_redirect_response=False,
            )

        with patch("constance.config", wraps=config, ALLOW_MODERATOR_LOGIN_AS_USER=True):
            self.assertEqual(self.client.get(staff_url).status_code, 403)
            self.assertContains(self.client.get(regular_url), f"<strong>{self.user.username}</strong>", html=True)
            self.assertRedirects(self.client.post(regular_url), "/index.php", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    @override_settings(ROOT_URLCONF="lunastore.urls_private", TELEGRAM_LOGGER_ENABLED=False)
    def test_impersonation_confirms_target_and_restores_admin(self):
        actor = User.objects.create_superuser(username="admin", email="admin@example.test")
        client = Client(enforce_csrf_checks=True)
        client.force_login(actor)
        url = reverse("admin:user_user_login_as_user", args=[self.user.pk])
        changelist = reverse("admin:user_user_changelist")
        response = client.get(url)
        self.assertContains(response, f"<strong>{self.user.username}</strong>", html=True)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(int(client.session["_auth_user_id"]), actor.pk)
        self.assertEqual(client.post(url).status_code, 403)

        response = client.post(url, {"csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value})
        self.assertRedirects(response, "/index.php", fetch_redirect_response=False)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(client.session["impersonated_by"], actor.pk)

        with self.settings(ROOT_URLCONF="lunastore.urls"):
            page = client.get(response.url)
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.wsgi_request.user.pk, self.user.pk)
            response = client.post(reverse("revert_impersonation"), {
                "csrfmiddlewaretoken": client.cookies[settings.CSRF_COOKIE_NAME].value,
            })
        self.assertRedirects(response, changelist, fetch_redirect_response=False)
        self.assertEqual(int(client.session["_auth_user_id"]), actor.pk)
        self.assertNotIn("impersonated_by", client.session)

    @patch("apps.user.views.process_login_notification")
    def test_web_totp_cannot_be_reused_for_jwt(self, notification_task):
        self.user.totp_enabled = True
        self.user.totp_secret = pyotp.random_base32()
        self.user.save(update_fields=["totp_enabled", "totp_secret"])
        cache.clear()
        credentials = {"username": self.user.username, "password": "original-password"}
        with patch("apps.user.services.login_security.time.time", return_value=1_800_000_000):
            code = pyotp.TOTP(self.user.totp_secret).generate_otp(1_800_000_000 // 30)
            self.assertRedirects(
                self.client.post(reverse("login"), credentials), reverse("two_factor_attempt"),
                fetch_redirect_response=False,
            )
            self.assertRedirects(
                self.client.post(reverse("two_factor_attempt"), {"2fa-code": code}), reverse("home"),
                fetch_redirect_response=False,
            )
            response = APIClient().post(
                "/method/v2/auth/token/", {**credentials, "totp_code": code}, format="json",
            )
        notification_task.enqueue.assert_called_once()
        self.assertEqual(response.status_code, 401)
        self.assertFalse(APISession.objects.filter(user=self.user).exists())

    def test_access_after_rotation_is_revoked_with_session(self):
        pair = issue_tokens(self.user)
        rotated = rotate_tokens(pair["refresh"])
        auth = CustomJWTAuthentication()
        for access in (pair["access"], rotated["access"]):
            self.assertEqual(auth.get_user(auth.get_validated_token(access)), self.user)
        APISession.objects.filter(user=self.user).update(revoked_at=self.user.date_joined)
        for access in (pair["access"], rotated["access"]):
            with self.assertRaises(InvalidToken):
                auth.get_user(auth.get_validated_token(access))
        with self.assertRaises(InvalidToken):
            rotate_tokens(rotated["refresh"])

    def test_password_change_invalidates_access_and_refresh(self):
        pair = issue_tokens(self.user)
        self.user.set_password("different-password")
        self.user.save(update_fields=["password"])
        auth = CustomJWTAuthentication()
        with self.assertRaises(InvalidToken):
            auth.get_user(auth.get_validated_token(pair["access"]))
        with self.assertRaises(InvalidToken):
            rotate_tokens(pair["refresh"])

    def test_unbanning_does_not_restore_tokens(self):
        pair = issue_tokens(self.user)
        ban = UserBan.objects.create(user=self.user, is_permanent=True, reason="test")
        ban.delete()
        with self.assertRaises(InvalidToken):
            rotate_tokens(pair["refresh"])

    @override_settings(
        OIDC_EXPECTED_ISSUER="https://issuer.example.test", OIDC_REQUIRED_ROLE="staff",
        OIDC_RP_CLIENT_ID="lunastore", OIDC_OP_TOKEN_ENDPOINT="https://issuer.example.test/token",
        OIDC_OP_USER_ENDPOINT="https://issuer.example.test/userinfo",
        OIDC_OP_JWKS_ENDPOINT="https://issuer.example.test/jwks",
    )
    def test_oidc_requires_role_and_manual_binding(self):
        backend = OIDCModel()
        backend.request = RequestFactory().get("/")
        backend.request.session = {}
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        payload = {
            "iss": "https://issuer.example.test", "sub": "account", "aud": "lunastore",
            "exp": int(time.time()) + 60,
        }
        with patch.object(backend, "get_userinfo", return_value={"sub": "account", "groups": ["staff"]}):
            with self.assertRaises(SuspiciousOperation):
                backend.get_or_create_user("access", "id", payload)
            OIDCIdentity.objects.create(user=self.user, issuer=payload["iss"], subject=payload["sub"])
            self.assertEqual(backend.get_or_create_user("access", "id", payload), self.user)
        with patch.object(backend, "get_userinfo", return_value={"sub": "account", "groups": []}):
            with self.assertRaises(SuspiciousOperation):
                backend.get_or_create_user("access", "id", payload)


class ConcurrentRefreshTests(TransactionTestCase):
    def test_only_one_rotation_can_use_the_same_refresh_token(self):
        user = User.objects.create_user(username="rotator", email="rotator@example.test")
        pair = issue_tokens(user)
        barrier = Barrier(2, timeout=10)

        def refresh():
            close_old_connections()
            try:
                barrier.wait()
                rotate_tokens(pair["refresh"])
                return True
            except InvalidToken:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            attempts = [executor.submit(refresh) for _ in range(2)]
            self.assertEqual(sorted(attempt.result(timeout=15) for attempt in attempts), [False, True])
