from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.gis.geoip2 import GeoIP2

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

def force_logout(user):
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now())
    for session in active_sessions:
        data = session.get_decoded()
        if str(user.pk) == data.get("_auth_user_id"):
            session.delete()

def get_location_geoip(ip):
    g = GeoIP2()
    try:
        city_data = g.city(ip)
        return f"{city_data['city']}, {city_data['country_name']}"
    except Exception:
        return "Unknown"
