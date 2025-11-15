from django.utils.deprecation import MiddlewareMixin
from .models import UserBan

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class BlockBannedIP(MiddlewareMixin):
    _banned_ips = None
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.refresh_banned_ips()
        
    @classmethod
    def refresh_banned_ips(cls):
        cls._banned_ips = set(
            UserBan.objects.values_list('ip', flat=True)
        )
        print(f"[BlockBannedIP | MDW] loaded {len(cls._banned_ips)} banned IPs")
        
    @classmethod
    def get_banned_set(cls):
        if cls._banned_ips is None:
            print("[BlockBannedIP | MDW] banned IPs cache is empty, refreshing...")
            cls.refresh_banned_ips()
            print(f"[BlockBannedIP | MDW] banned IPs cache refreshed, total {len(cls._banned_ips)} banned IPs")
        return cls._banned_ips
                