# centralized dynamic config helpers for clickhouse analytics

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger("analytics")

DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 30
DEFAULT_FLUSH_THRESHOLD = 500
DEFAULT_BUFFER_MAX_SIZE = 100_000
DEFAULT_FLUSH_BATCH_SIZE = 1000
DEFAULT_FLUSH_INTERVAL = 5.0


def _is_mock(val: Any) -> bool:
    return hasattr(val, "_mock_return_value") or getattr(type(val), "__module__", "").startswith("unittest.mock")


def get_config_value(key: str, default: Any, cast_type: type = str) -> Any:
    # constance dynamic config
    try:
        from constance import config

        val = getattr(config, key, None)
        if val is not None and not _is_mock(val):
            return cast_type(val)
    except Exception:
        pass

    # settings fallback
    try:
        val = getattr(settings, key, None)
        if val is not None and not _is_mock(val):
            return cast_type(val)
    except Exception:
        pass

    return default


def get_circuit_breaker_timeout() -> int:
    val = int(get_config_value("ANALYTICS_CIRCUIT_BREAKER_TIMEOUT", DEFAULT_CIRCUIT_BREAKER_TIMEOUT, int))
    return max(1, min(86400, val))


def get_flush_threshold() -> int:
    val = int(get_config_value("ANALYTICS_FLUSH_THRESHOLD", DEFAULT_FLUSH_THRESHOLD, int))
    return max(1, min(100_000, val))


def get_buffer_max_size() -> int:
    val = int(get_config_value("ANALYTICS_BUFFER_MAX_SIZE", DEFAULT_BUFFER_MAX_SIZE, int))
    return max(100, min(10_000_000, val))


def get_flush_batch_size() -> int:
    val = int(get_config_value("ANALYTICS_FLUSH_BATCH_SIZE", DEFAULT_FLUSH_BATCH_SIZE, int))
    return max(1, min(50_000, val))


def get_flush_interval() -> float:
    val = float(get_config_value("ANALYTICS_FLUSH_INTERVAL", DEFAULT_FLUSH_INTERVAL, float))
    return max(0.1, min(3600.0, val))
