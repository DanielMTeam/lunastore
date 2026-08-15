# safe request metadata extractor for analytics events

from __future__ import annotations

import logging
from typing import Any, Optional

from django.http import HttpRequest

from apps.core.utils import get_client_ip, get_country_code

logger = logging.getLogger("analytics")


def extract_request_meta(request: Optional[HttpRequest]) -> dict[str, Any]:
    # return normalized, length-bounded client metadata from request
    if request is None:
        return {
            "user_id": None,
            "ip": "",
            "country": "",
            "os_name": "",
            "os_version": "",
            "browser": "",
            "referer": "",
            "session_id": "",
        }

    # resolve authenticated user id
    user_id: Optional[int] = None
    try:
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            user_id = int(user.pk)
    except Exception:
        logger.debug("failed to resolve user_id from request", exc_info=True)

    # resolve client ip
    ip = ""
    try:
        resolved_ip = get_client_ip(request)
        if resolved_ip:
            ip = str(resolved_ip).strip()[:45]
    except Exception:
        logger.debug("failed to resolve client ip", exc_info=True)

    # resolve country (geoip or cloudflare header)
    country = ""
    if ip:
        try:
            cf_country = request.META.get("HTTP_CF_IPCOUNTRY", "").strip()
            if cf_country and cf_country != "XX" and len(cf_country) <= 4:
                country = cf_country.upper()
            else:
                code = get_country_code(ip)
                if code and code != "Unknown":
                    country = str(code).strip()[:8].upper()
        except Exception:
            logger.debug("failed to resolve country code for ip=%s", ip, exc_info=True)

    # resolve os & browser from user-agent
    os_name = ""
    os_version = ""
    browser = ""
    try:
        user_agent_obj = getattr(request, "user_agent", None)
        if user_agent_obj is None:
            raw_ua = request.META.get("HTTP_USER_AGENT", "").strip()
            if raw_ua:
                from user_agents import parse

                user_agent_obj = parse(raw_ua)

        if user_agent_obj:
            os_family = getattr(user_agent_obj.os, "family", "") or ""
            os_ver = getattr(user_agent_obj.os, "version_string", "") or ""
            browser_family = getattr(user_agent_obj.browser, "family", "") or ""
            browser_ver = getattr(user_agent_obj.browser, "version_string", "") or ""

            os_name = str(os_family).strip()[:64]
            os_version = str(os_ver).strip()[:32]
            browser = (
                f"{browser_family} {browser_ver}".strip()[:64]
                if browser_family
                else ""
            )
    except Exception:
        logger.debug("failed to parse user_agent", exc_info=True)

    # resolve referer & session
    referer = str(request.META.get("HTTP_REFERER", "")).strip()[:500]

    session_id = ""
    try:
        session = getattr(request, "session", None)
        if session and getattr(session, "session_key", None):
            session_id = str(session.session_key).strip()[:64]
    except Exception:
        logger.debug("failed to extract session_key", exc_info=True)

    return {
        "user_id": user_id,
        "ip": ip,
        "country": country,
        "os_name": os_name,
        "os_version": os_version,
        "browser": browser,
        "referer": referer,
        "session_id": session_id,
    }
