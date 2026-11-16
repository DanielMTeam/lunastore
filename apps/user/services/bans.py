from ipaddress import ip_address

from django.db.models import Q
from django.utils import timezone

from apps.user.models import UserBan


def active_bans():
    return UserBan.objects.filter(
        Q(is_permanent=True) | Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )


def is_ip_banned(ip):
    try:
        ip = str(ip_address(ip))
    except ValueError:
        return False
    return active_bans().filter(ip=ip, ban_by_ip=True).exists()
