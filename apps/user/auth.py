import time

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, login
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import OIDCIdentity
from .services.bans import active_bans, is_ip_banned
from apps.core.utils import get_client_ip


class OIDCModel(OIDCAuthenticationBackend):
    def get_or_create_user(self, access_token, id_token, payload):
        issuer = settings.OIDC_EXPECTED_ISSUER
        role = settings.OIDC_REQUIRED_ROLE
        subject = payload.get("sub")
        audience = payload.get("aud")
        if isinstance(audience, str):
            audience = [audience]
        expires_at = payload.get("exp")
        client_id = settings.OIDC_RP_CLIENT_ID
        if (
            not issuer or not role or payload.get("iss") != issuer
            or not isinstance(subject, str) or not subject or len(subject) > 255
            or not client_id or not isinstance(audience, list) or client_id not in audience
            or (len(audience) > 1 and payload.get("azp") != client_id)
            or ("azp" in payload and payload["azp"] != client_id)
            or type(expires_at) is not int or expires_at <= time.time()
        ):
            raise SuspiciousOperation("Invalid OIDC identity claims.")

        claims = self.get_userinfo(access_token, id_token, payload)
        groups = claims.get("groups")
        if claims.get("sub") != subject or not isinstance(groups, list) or role not in groups:
            raise SuspiciousOperation("OIDC role required.")

        identity = OIDCIdentity.objects.select_related("user").filter(issuer=issuer, subject=subject).first()
        if identity is None:
            raise SuspiciousOperation("OIDC account has no local binding.")
        user = identity.user
        if not user.is_staff or not user.is_active or user.deleted or (
            active_bans().filter(user=user).exists() or is_ip_banned(get_client_ip(self.request))
        ):
            raise SuspiciousOperation("OIDC account is unavailable.")

        return user


class BoundOIDCCallbackView(OIDCAuthenticationCallbackView):
    def login_success(self):
        backend_path = "apps.user.auth.OIDCModel"
        if self.request.session.get(BACKEND_SESSION_KEY) != backend_path or self.request.user != self.user:
            login(self.request, self.user, backend=backend_path)
        response = super().login_success()
        self.request.session["oidc_identity_bound"] = True
        return response
