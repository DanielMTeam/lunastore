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


def lunapassport_settings(request):
    from apps.user.services import lunapassport as passport_svc
    return {"lunapassport_enabled": passport_svc.is_enabled()}


def geo_domains_processor(request):
    from apps.core.utils import get_geo_domains
    return {"geo_domains": get_geo_domains(request)}


def notification_context(request):
    from apps.user.decorators import is_modern_browser
    is_modern = is_modern_browser(request)
    if request.user.is_authenticated:
        from apps.core.utils import get_geo_domains
        geo_domains = get_geo_domains(request)
        api_url = geo_domains.get('SPIRE_URL', settings.LUNASPIRE_URL)
        return {
            'is_modern_browser': is_modern,
            'notify_token': NotificationService.get_receive_token(
                request.user.id),
            'api_url': api_url,
        }
    return {
        'is_modern_browser': is_modern,
    }
