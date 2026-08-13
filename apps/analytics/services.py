# public analytics api for the rest of the project

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from apps.analytics.reporting import (
    AnalyticsUnavailableError,
    report_analytics_error,
)

logger = logging.getLogger("analytics")


def is_enabled() -> bool:
    # constance first, settings as fallback
    try:
        from constance import config

        return bool(config.ANALYTICS_ENABLED)
    except Exception:
        try:
            from django.conf import settings

            return bool(getattr(settings, "ANALYTICS_ENABLED", False))
        except Exception:
            logger.debug("failed to resolve ANALYTICS_ENABLED", exc_info=True)
            return False


def ping() -> bool:
    # quick "is clickhouse up" check
    if not is_enabled():
        logger.debug("analytics ping skipped: disabled")
        return False

    from apps.analytics.client import get_analytics_client

    try:
        client = get_analytics_client(force_enabled=True)
        return client.ping()
    except AnalyticsUnavailableError as exc:
        report_analytics_error(exc, "analytics ping unavailable")
        return False


def track_event(
    event_name: str,
    *,
    user_id: Optional[int] = None,
    event_time: Optional[datetime] = None,
    properties: Optional[Mapping[str, Any]] = None,
) -> None:
    # enqueue insert via django.tasks; no-op when analytics is off
    if not is_enabled():
        logger.debug(
            "track_event skipped: analytics disabled name=%s",
            event_name,
        )
        return

    if not event_name:
        logger.warning("track_event skipped: empty event_name")
        return

    from apps.analytics.tasks import insert_analytics_event

    props = dict(properties) if properties else {}
    try:
        insert_analytics_event.enqueue(
            event_name,
            user_id,
            event_time.isoformat() if event_time is not None else None,
            props,
        )
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to enqueue analytics event name={event_name}",
        )
