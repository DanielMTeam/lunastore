from unittest.mock import patch

import jwt
import pyotp
import requests
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.api.token_sessions import issue_tokens
from apps.user.models import User


@override_settings(ROOT_URLCONF="lunastore.urls_api", MEILISEARCH_ENABLED=False)
class AccountContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="mobile-user", email="mobile@example.test", password="mobile-test-password",
        )
        cls.other = User.objects.create_user(username="other-user", email="other@example.test")

    def authenticate_as(self, user):
        pair = issue_tokens(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair['access']}")
        return pair

    def test_profile_is_read_only_and_uses_token_owner(self):
        url = "/v3/me/"
        self.assertEqual(self.client.get(url).status_code, 401)
        for user in (self.user, self.other):
            self.authenticate_as(user)
            profile = self.client.get(url, {"user_id": self.other.pk})
            self.assertEqual(profile.data["id"], user.pk)
            self.assertIn("no-store", profile["Cache-Control"])
        self.assertEqual(self.client.patch(url, {"username": "changed"}).status_code, 405)

    def test_login_rotate_and_revoke(self):
        login = self.client.post("/v3/auth/token/", {
            "username": self.user.username, "password": "mobile-test-password",
        }, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        original = login.data
        refresh_url = "/v3/auth/token/refresh/"
        rotated = self.client.post(refresh_url, {"refresh": original["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200, rotated.data)
        self.assertEqual(self.client.post(refresh_url, {"refresh": original["refresh"]}, format="json").status_code, 401)
        revoke = self.client.post("/v3/auth/token/revoke/", {"refresh": rotated.data["refresh"]}, format="json")
        self.assertEqual(revoke.status_code, 204, revoke.data)
        for access in (original["access"], rotated.data["access"]):
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
            self.assertEqual(self.client.get("/v3/me/").status_code, 401)

    def test_login_supports_totp(self):
        self.user.totp_secret = pyotp.random_base32()
        self.user.totp_enabled = True
        self.user.save(update_fields=["totp_secret", "totp_enabled"])
        credentials = {"username": self.user.username, "password": "mobile-test-password"}
        url = "/v3/auth/token/"
        required = self.client.post(url, credentials, format="json")
        self.assertEqual(required.status_code, 401, required.data)
        credentials["totp_code"] = pyotp.TOTP(self.user.totp_secret).now()
        accepted = self.client.post(url, credentials, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)

    @patch("apps.api.v3.account.NotificationService.mark_all_read")
    @patch("apps.api.v3.account.NotificationService.list_notifications")
    def test_notification_list_and_repeated_mark_are_scoped_to_owner(self, list_notifications, mark):
        self.authenticate_as(self.user)
        list_notifications.return_value = {
            "total": 2, "total_unread": 1, "data": [
                {"ID": 1, "Title": "Ready", "Content": "Download available", "Meta": {"type": "info"},
                 "CreatedAt": 1800000000, "ViewedAt": None},
            ],
        }
        url = "/v3/me/notifications/"
        result = self.client.get(url, {"limit": 1, "user_id": self.other.pk})
        self.assertEqual(result.status_code, 200, result.data)
        list_notifications.assert_called_once_with(self.user.pk, page=1, limit=1)
        mark.assert_not_called()
        self.assertEqual(result.data["unread_count"], 1)
        self.assertIsNone(result.data["results"][0]["read_at"])
        self.assertTrue(result.data["results"][0]["created_at"].endswith("Z"))
        self.assertTrue(result.data["next"].endswith("?page=2&limit=1"))
        for _ in range(2):
            marked = self.client.post(f"{url}mark-all-read/", {"user_id": self.other.pk}, format="json")
            self.assertEqual(marked.status_code, 204, marked.data)
        self.assertEqual([call.args for call in mark.call_args_list], [(self.user.pk,), (self.user.pk,)])

    @patch("apps.core.notifications.services.requests.request", side_effect=requests.Timeout)
    def test_lunaspire_timeout_returns_problem(self, upstream):
        self.authenticate_as(self.user)
        result = self.client.get("/v3/me/notifications/")
        self.assertEqual(result.status_code, 503, result.data)
        self.assertEqual(result.data["code"], "notifications_unavailable")
        self.assertEqual(result["Content-Type"], "application/problem+json")

    @override_settings(LUNASPIRE_SECRET_KEY="notifications-service-dummy-key-32")
    @patch("apps.core.notifications.services.requests.request")
    def test_upstream_rate_limit_preserves_retry_after_and_uses_service_token(self, upstream):
        self.authenticate_as(self.user)
        upstream.return_value.status_code = 429
        upstream.return_value.headers = {"Retry-After": "42"}
        for method, path in (
            (self.client.get, "/v3/me/notifications/"),
            (self.client.post, "/v3/me/notifications/mark-all-read/"),
        ):
            with self.subTest(path=path):
                result = method(path)
                self.assertEqual(result.status_code, 429)
                self.assertEqual(result["Retry-After"], "42")
                self.assertEqual(result.data["code"], "throttled")
                kwargs = upstream.call_args.kwargs
                self.assertNotIn("token", kwargs["params"])
                token = kwargs["headers"]["Authorization"].removeprefix("Bearer ")
                claims = jwt.decode(token, settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"])
                self.assertEqual(claims["type"], "notify-service")
                self.assertEqual(claims["user_id"], self.user.pk)
