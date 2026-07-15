from django.tasks import task
from django.core.cache import cache
from .models import UserBan, User
import logging
from apps.core.utils import get_client_ip, get_location_geoip
from user_agents import parse
from django.contrib.gis.geoip2 import GeoIP2
from django.utils.translation import gettext_lazy as _
from apps.core.notifications.services import NotificationService

logger = logging.getLogger('user')


CACHE_KEY = 'banned_ips_list'
CACHE_TIMEOUT = 60 * 1  # 5 minutes


@task
def refresh_banned_ips_cache():
    banned_ips = set(UserBan.objects.values_list('ip', flat=True))
    cache.set(CACHE_KEY, banned_ips, timeout=CACHE_TIMEOUT)
    logging.info(
        f"[User APP; Tasks] Refreshed banned IPs cache with {
            len(banned_ips)} entries.")


@task()
def process_login_notification(user_id, ip, user_agent):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    # parse user agent
    ua = parse(user_agent)
    browser = ua.browser.family if ua.browser.family != "Other" else "Unknown"
    os_name = ua.os.family if ua.os.family != "Other" else "Unknown OS"

    # find location by IP
    try:
        city_data = GeoIP2().city(ip)
        location = f"{city_data['city']}, {city_data['country_name']}"
    except Exception:
        location = "Неизвестная локация"

    # form context
    context = {
        'browser': browser,
        'os': os_name,
        'ip': ip,
        'location': location,
    }

    # send notification
    NotificationService.send_notification(
        user_id=user.id,
        title=str(_("NOTIF_LOGIN_TITLE")),
        content=str(_("NOTIF_LOGIN_DESCRIPTION")) % context,
        meta={
            "type": "warning",
            "device_info": context
        }
    )
