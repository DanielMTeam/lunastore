from django.utils.deprecation import MiddlewareMixin
from .models import UserBan
from .tasks import refresh_banned_ips_cache, CACHE_KEY
from django.http import HttpResponseForbidden
from django.core.cache import cache
import logging
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('user')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class BlockBannedIP(MiddlewareMixin):
    def process_request(self, request):
        ip = get_client_ip(request)
        banned_ips = cache.get(CACHE_KEY)
        if banned_ips is None:
            refresh_banned_ips_cache.enqueue() 
            from .models import UserBan
            banned_ips = set(UserBan.objects.values_list('ip', flat=True))
            cache.set(CACHE_KEY, banned_ips, timeout=60*5)

        if ip in banned_ips:
            return HttpResponseForbidden(_("INFO_YOUR_IP_WAS_BANNED"))

    @classmethod
    def get_banned_set(cls):
        banned_ips = cache.get(CACHE_KEY)
        
        if banned_ips is None:
            logging.info("[BlockBannedIP] Cache miss. Fetching from DB directly...")
            
            from .models import UserBan 
            
            banned_ips = set(UserBan.objects.values_list('ip', flat=True))
            
            cache.set(CACHE_KEY, banned_ips, timeout=300)
            
            try:
                refresh_banned_ips_cache.enqueue()
            except Exception as e:
                logging.error(f"Task enqueue failed: {e}")

        return banned_ips