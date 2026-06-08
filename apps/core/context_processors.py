from constance import config
from django.conf import settings

from .models import Banner
from apps.core.dynamic_settings import get_motd_list
from apps.core.notifications.services import NotificationService

def random_banner(request):
    banner = Banner.objects.filter(is_active=True).order_by("?").first()
    return {"sidebar_banner": banner}


def motd_processor(request):
    return {"motds": get_motd_list()}


def drm_settings(request):
    return {"ENABLE_DRM": config.ENABLE_DRM}

def geo_domains_processor(request):
    return {"geo_domains": getattr(request, 'geo_domains', {})}

def notification_context(request):
    if request.user.is_authenticated:
        geo_domains = getattr(request, 'geo_domains', {})
        api_url = geo_domains.get('API_URL', settings.LUNASPIRE_URL)
        return {
            'notify_token': NotificationService.get_receive_token(request.user.id),
            'api_url': api_url
        }
    return {}
