"""drf throttle classes that resolve the real client ip behind proxies."""

from __future__ import annotations

from typing import Any

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from apps.core.utils import get_client_ip


class RealIPAnonRateThrottle(AnonRateThrottle):
    """anonymous throttle keyed by real client ip (cloudflare / x-real-ip aware)."""

    def get_ident(self, request: Any) -> str:
        # prefer cf-connecting-ip / x-real-ip / x-forwarded-for over num_proxies math
        ip = get_client_ip(request)
        if ip:
            return ip
        return super().get_ident(request)


class RealIPUserRateThrottle(UserRateThrottle):
    """authenticated throttle; falls back to real client ip when anonymous."""

    def get_ident(self, request: Any) -> str:
        ip = get_client_ip(request)
        if ip:
            return ip
        return super().get_ident(request)
