"""drf throttle classes with real client ip and live constance rates."""

from __future__ import annotations

import logging
from typing import Any, Optional

from constance import config
from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from apps.core.utils import get_client_ip

logger = logging.getLogger(__name__)

_VALID_PERIODS = frozenset({"s", "sec", "m", "min", "h", "hour", "d", "day"})


def _fallback_rate(scope: str) -> str:
    """return default throttle rate from rest framework settings."""
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    defaults = {"anon": "1000/hour", "user": "5000/hour"}
    return str(rates.get(scope) or defaults[scope])


def _is_valid_rate(rate: str) -> bool:
    """validate drf-style rate string like '1000/hour'."""
    try:
        num, period = rate.split("/")
        int(num)
        return period.strip().lower() in _VALID_PERIODS or period.strip().lower()[0] in {
            "s",
            "m",
            "h",
            "d",
        }
    except (TypeError, ValueError, IndexError, AttributeError):
        return False


def resolve_throttle_rate(constance_key: str, scope: str) -> str:
    """read live rate from constance with validation and settings fallback."""
    fallback = _fallback_rate(scope)
    try:
        raw = getattr(config, constance_key, fallback)
        rate = str(raw or "").strip()
        if _is_valid_rate(rate):
            return rate
        logger.warning(
            "invalid %s value %r, falling back to %s",
            constance_key,
            raw,
            fallback,
        )
    except Exception:
        logger.exception("failed to read %s from constance", constance_key)
    return fallback


def is_api_throttle_enabled() -> bool:
    """whether drf api throttles are enabled (live via constance)."""
    try:
        return bool(getattr(config, "API_THROTTLE_ENABLED", True))
    except Exception:
        logger.exception("failed to read API_THROTTLE_ENABLED")
        return True


class RealIPMixin:
    """resolve client identity via cloudflare / proxy-aware helpers."""

    def get_ident(self, request: Any) -> str:
        ip = get_client_ip(request)
        if ip:
            return ip
        return super().get_ident(request)  # type: ignore[misc]


class RealIPAnonRateThrottle(RealIPMixin, AnonRateThrottle):
    """anonymous throttle: real ip + constance-configurable rate."""

    scope = "anon"

    def get_rate(self) -> Optional[str]:
        return resolve_throttle_rate("API_THROTTLE_ANON_RATE", self.scope)

    def allow_request(self, request: Any, view: Any) -> bool:
        if not is_api_throttle_enabled():
            return True
        # re-bind rate each request so constance edits apply without reload
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


class RealIPUserRateThrottle(RealIPMixin, UserRateThrottle):
    """user throttle: real ip fallback + constance-configurable rate."""

    scope = "user"

    def get_rate(self) -> Optional[str]:
        return resolve_throttle_rate("API_THROTTLE_USER_RATE", self.scope)

    def allow_request(self, request: Any, view: Any) -> bool:
        if not is_api_throttle_enabled():
            return True
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
