from django.conf import settings

from .models import Banner


def random_banner(request):
    banner = Banner.objects.filter(is_active=True).order_by("?").first()
    return {"sidebar_banner": banner}


def motd_processor(request):
    return {"motds": getattr(settings, "MOTD_LIST", ["Windows XP Professional"])}


def drm_settings(request):
    return {"ENABLE_DRM": getattr(settings, "ENABLE_DRM", False)}
