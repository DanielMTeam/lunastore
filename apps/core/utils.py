import ipaddress
import logging
from typing import Iterable, Optional

from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.gis.geoip2 import GeoIP2
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


def _parse_proxy_networks() -> list:
    # parse TRUSTED_PROXIES setting into ip networks
    raw = getattr(settings, "TRUSTED_PROXIES", None) or []
    if isinstance(raw, str):
        items = [p.strip() for p in raw.split(";") if p.strip()]
    else:
        items = [str(p).strip() for p in raw if str(p).strip()]

    networks = []
    for item in items:
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("invalid trusted proxy entry skipped: %s", item)
    return networks


def _ip_in_networks(ip_str: str, networks: Iterable) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in network for network in networks)


def get_client_ip(request) -> Optional[str]:
    # return client ip. proxy headers are trusted only when REMOTE_ADDR
    # belongs to TRUSTED_PROXIES (cidr/ip list from settings/env)
    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    networks = _parse_proxy_networks()

    if networks and remote_addr and _ip_in_networks(remote_addr, networks):
        for header in (
            "HTTP_CF_CONNECTING_IP",
            "HTTP_X_REAL_IP",
            "HTTP_X_FORWARDED_FOR",
        ):
            value = request.META.get(header)
            if not value:
                continue
            candidate = value.split(",")[0].strip()
            if candidate:
                return candidate

    return remote_addr or None


def get_safe_redirect_url(request, candidate: Optional[str], fallback: str = "/") -> str:
    # validate redirect target against open-redirect attacks
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def force_logout(user):
    from apps.user.models import UserSession
    user_sessions = UserSession.objects.filter(user=user)
    session_keys = [us.session_key for us in user_sessions]
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
        user_sessions.delete()


def get_location_geoip(ip: str) -> str:
    # resolve city/country for ip; return Unknown if mmdb missing or invalid
    try:
        g = GeoIP2()
        city_data = g.city(ip)
        return f"{city_data['city']}, {city_data['country_name']}"
    except Exception as exc:
        logger.warning("geoip location lookup failed for %s: %s", ip, exc)
        return "Unknown"


def get_country_code(ip: str) -> str:
    # resolve country code for ip; return Unknown if mmdb missing or invalid
    try:
        g = GeoIP2()
        city_data = g.city(ip)
        return city_data.get('country_code', 'Unknown')
    except Exception as exc:
        logger.warning("geoip country lookup failed for %s: %s", ip, exc)
        return "Unknown"
