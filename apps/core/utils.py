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
    from apps.user.models import UserSession
    user_sessions = UserSession.objects.filter(user=user)
    session_keys = [us.session_key for us in user_sessions]
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
        user_sessions.delete()

def get_location_geoip(ip):
    g = GeoIP2()
    try:
        city_data = g.city(ip)
        return f"{city_data['city']}, {city_data['country_name']}"
    except Exception:
        return "Unknown"

def get_country_code(ip):
    g = GeoIP2()
    try:
        city_data = g.city(ip)
        return city_data.get('country_code', 'Unknown')
    except Exception:
        return "Unknown"
