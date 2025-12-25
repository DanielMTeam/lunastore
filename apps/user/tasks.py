from django.tasks import task
from django.core.cache import cache
from .models import UserBan, User
import logging

logger = logging.getLogger('user')


CACHE_KEY = 'banned_ips_list'
CACHE_TIMEOUT = 60 * 1  # 5 minutes


@task 
def refresh_banned_ips_cache():
    banned_ips = set(UserBan.objects.values_list('ip', flat=True))
    cache.set(CACHE_KEY, banned_ips, timeout=CACHE_TIMEOUT)
    logging.info(f"[User APP; Tasks] Refreshed banned IPs cache with {len(banned_ips)} entries.")

