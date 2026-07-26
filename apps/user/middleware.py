import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from apps.core.utils import get_client_ip

from .tasks import CACHE_KEY, refresh_banned_ips_cache

logger = logging.getLogger("user")


class BlockBannedIP(MiddlewareMixin):
    def process_request(self, request):
        ip = get_client_ip(request)
        banned_ips = self.get_banned_set()

        if ip in banned_ips:
            context = {
                "admin_email": getattr(
                    settings,
                    "ADMIN_EMAIL",
                    "support@example.com")}
            return render(request, "banned_ip.html", context, status=403)

    @classmethod
    def get_banned_set(cls):
        banned_ips = cache.get(CACHE_KEY)

        if banned_ips is None:
            logging.info(
                "[BlockBannedIP] Cache miss. Fetching from DB directly...")
            from .models import UserBan

            now = timezone.now()

            active_bans = UserBan.objects.filter(
                Q(ban_by_ip=True),
                ~Q(ip__isnull=True),
                Q(is_permanent=True) | Q(expires_at__gt=now),
            ).values_list("ip", flat=True)

            banned_ips = set(active_bans)

            cache.set(CACHE_KEY, banned_ips, timeout=300)

            try:
                refresh_banned_ips_cache.enqueue()
            except Exception as e:
                logging.error(f"Task enqueue failed: {e}")

        return banned_ips


class UserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
