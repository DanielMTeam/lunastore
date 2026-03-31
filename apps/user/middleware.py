import logging

from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext_lazy as _

from .tasks import CACHE_KEY, refresh_banned_ips_cache

logger = logging.getLogger("user")


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


class BlockBannedIP(MiddlewareMixin):
    def process_request(self, request):
        ip = get_client_ip(request)
        banned_ips = self.get_banned_set()

        if ip in banned_ips:
            context = {
                "admin_email": getattr(settings, "ADMIN_EMAIL", "support@example.com")
            }
            return render(request, "banned_ip.html", context, status=403)

    @classmethod
    def get_banned_set(cls):
        banned_ips = cache.get(CACHE_KEY)

        if banned_ips is None:
            logging.info("[BlockBannedIP] Cache miss. Fetching from DB directly...")
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
