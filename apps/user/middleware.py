import logging

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from apps.core.utils import get_client_ip

from .services.bans import is_ip_banned

logger = logging.getLogger("user")


class BlockBannedIP(MiddlewareMixin):
    def process_request(self, request):
        ip = get_client_ip(request)
        if is_ip_banned(ip):
            context = {
                "admin_email": getattr(
                    settings,
                    "ADMIN_EMAIL",
                    "support@example.com")}
            return render(request, "banned_ip.html", context, status=403)


class UserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.core.local import set_current_request
        from apps.core.utils import get_geo_domains
        set_current_request(request)
        get_geo_domains(request)

        if request.user.is_authenticated:
            from django.contrib.auth import BACKEND_SESSION_KEY, logout
            from .services.bans import active_bans

            legacy_oidc = (
                request.session.get(BACKEND_SESSION_KEY) == "apps.user.auth.OIDCModel"
                and "oidc_id_token_expiration" in request.session
                and not request.session.get("oidc_identity_bound")
            )
            if legacy_oidc or active_bans().filter(user=request.user).exists():
                logout(request)

        if request.user.is_authenticated and request.session.session_key:
            session_key = request.session.session_key

            from .models import UserSession
            client_ip = get_client_ip(request) or ""
            user_session, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={
                    "user": request.user,
                    "ip": client_ip,
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255]
                }
            )

            if not created:
                # Update last_activity if more than 5 minutes have passed
                if (timezone.now() -
                        user_session.last_activity).total_seconds() > 300:
                    user_session.last_activity = timezone.now()
                    user_session.ip = client_ip
                    user_session.user_agent = request.META.get(
                        "HTTP_USER_AGENT", "")[:255]
                    user_session.save(
                        update_fields=[
                            'last_activity',
                            'ip',
                            'user_agent'])

        response = self.get_response(request)
        return response
