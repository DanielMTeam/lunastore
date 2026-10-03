import ipaddress
import json
import logging
import re
from typing import Iterable, Optional

from constance import config
from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.gis.geoip2 import GeoIP2
from django.core.cache import cache
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


def _is_loopback_or_private(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return addr.is_loopback or addr.is_private
    except ValueError:
        return False


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


# cached geoip reader; unavailable flag avoids retrying a broken mmdb every request
_geoip_reader: Optional[GeoIP2] = None
_geoip_unavailable: bool = False


def _get_geoip() -> Optional[GeoIP2]:
    # return GeoIP2 reader or None when database is missing/invalid
    global _geoip_reader, _geoip_unavailable
    if _geoip_unavailable:
        return None
    if _geoip_reader is not None:
        return _geoip_reader
    try:
        _geoip_reader = GeoIP2()
        return _geoip_reader
    except Exception as exc:
        _geoip_unavailable = True
        logger.warning("geoip database unavailable, lookups disabled: %s", exc)
        return None


def get_location_geoip(ip: str) -> str:
    # resolve city/country for ip; return Unknown if mmdb missing or invalid
    g = _get_geoip()
    if g is None:
        return "Unknown"
    try:
        city_data = g.city(ip)
        return f"{city_data['city']}, {city_data['country_name']}"
    except Exception as exc:
        logger.debug("geoip location lookup failed for %s: %s", ip, exc)
        return "Unknown"


def get_country_code(ip: str) -> str:
    # resolve country code for ip; return Unknown if mmdb missing or invalid
    g = _get_geoip()
    if g is None:
        return "Unknown"
    try:
        city_data = g.city(ip)
        return city_data.get('country_code', 'Unknown')
    except Exception as exc:
        logger.debug("geoip country lookup failed for %s: %s", ip, exc)
        return "Unknown"


def get_country_from_request(request) -> str:
    # resolve country from reverse proxy headers (nginx/cloudflare/caddy) or cached geoip
    if not request:
        return "Unknown"

    remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
    networks = _parse_proxy_networks()
    if networks:
        trust_headers = bool(remote_addr) and _ip_in_networks(remote_addr, networks)
    else:
        trust_headers = bool(remote_addr) and _is_loopback_or_private(remote_addr)

    if trust_headers:
        for header in (
            "HTTP_X_COUNTRY_CODE",
            "HTTP_CF_IPCOUNTRY",
            "HTTP_X_GEOIP_COUNTRY",
            "HTTP_X_GEOIP_COUNTRY_CODE",
        ):
            raw_val = (request.META.get(header) or "").strip().upper()
            if len(raw_val) == 2 and raw_val.isalpha() and raw_val != "XX":
                return raw_val

    # fallback for standalone / dev without reverse proxy
    client_ip = get_client_ip(request)
    if client_ip:
        cache_key = f"geoip_cc_{client_ip}"
        try:
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception:
            cached = None

        code = get_country_code(client_ip)
        res = "Unknown"
        if code and code != "Unknown":
            res = str(code).strip()[:8].upper()
        try:
            cache.set(cache_key, res, timeout=86400 if res != "Unknown" else 3600)
        except Exception:
            pass
        return res

    return "Unknown"


# in-memory cache of parsed overrides to avoid json.loads on every request
_parsed_geo_overrides: tuple[str, dict] = ("", {})


def get_geo_domains(request=None) -> dict[str, str]:
    # resolve regional domains from host or country code using cached overrides
    global _parsed_geo_overrides

    geo_domains = {
        "API_URL": settings.API_URL,
        "SPIRE_URL": settings.LUNASPIRE_URL,
    }

    if not request:
        return geo_domains

    if hasattr(request, "geo_domains") and isinstance(request.geo_domains, dict):
        return request.geo_domains

    if getattr(config, "GEO_DOMAIN_PROXY_ENABLED", True):
        raw_overrides = getattr(config, "GEO_DOMAIN_OVERRIDES", "{}")
        if _parsed_geo_overrides[0] != raw_overrides:
            try:
                _parsed_geo_overrides = (raw_overrides, json.loads(raw_overrides))
            except Exception:
                _parsed_geo_overrides = (raw_overrides, {})

        overrides = _parsed_geo_overrides[1]
        if overrides and isinstance(overrides, dict):
            try:
                current_host = request.get_host().split(":")[0]
            except Exception:
                current_host = ""

            country_code = get_country_from_request(request)

            # check if current host is already on a regional mirror
            matched_code = None
            for code, override_data in overrides.items():
                if isinstance(override_data, dict):
                    raw_base = override_data.get("BASE_URL") or ""
                    clean_base = re.sub(r"^https?://", "", raw_base, flags=re.IGNORECASE).rstrip("/")
                    if clean_base and clean_base.lower() == current_host.lower():
                        matched_code = code
                        break

            target_code = matched_code
            if not target_code:
                if country_code in overrides:
                    target_code = country_code
                elif country_code.lower() in overrides:
                    target_code = country_code.lower()

            if target_code and target_code in overrides:
                country_overrides = overrides[target_code]
                if isinstance(country_overrides, dict):
                    if "BASE_URL" in country_overrides:
                        raw_base = country_overrides["BASE_URL"]
                        geo_domains["BASE_URL"] = re.sub(
                            r"^https?://", "", raw_base, flags=re.IGNORECASE
                        ).rstrip("/")
                    if "API_URL" in country_overrides:
                        api_val = country_overrides["API_URL"]
                        geo_domains["API_URL"] = (
                            api_val
                            if api_val.startswith(("http://", "https://", "//"))
                            else f"https://{api_val}"
                        )
                    if "SPIRE_URL" in country_overrides:
                        spire_val = country_overrides["SPIRE_URL"]
                        geo_domains["SPIRE_URL"] = (
                            spire_val
                            if spire_val.startswith(("http://", "https://", "//"))
                            else f"https://{spire_val}"
                        )

    request.geo_domains = geo_domains
    return geo_domains
