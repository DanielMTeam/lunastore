# shared error reporting for analytics (log + optional sentry)

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger("analytics")


class AnalyticsUnavailableError(Exception):
    # clickhouse missing/unreachable while analytics is on
    pass


def report_analytics_error(
    exc: BaseException,
    message: str = "",
    *,
    level: str = "error",
) -> None:
    # always log; also ship to sentry when sentry is enabled
    log_fn = logger.error if level == "error" else logger.warning
    if message:
        log_fn("%s: %s", message, exc, exc_info=exc)
    else:
        log_fn("analytics error: %s", exc, exc_info=exc)

    if not getattr(settings, "SENTRY_ENABLED", False):
        return
    if not getattr(settings, "SENTRY_DSN", ""):
        return

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("module", "analytics")
            if message:
                scope.set_extra("analytics_message", message)
            sentry_sdk.capture_exception(exc)
    except Exception as sentry_exc:
        logger.debug("sentry capture failed: %s", sentry_exc)


def optional_user_id(user_id: Optional[int]) -> Optional[int]:
    # keep None as None for debug (do not coerce to 0)
    if user_id is None:
        return None
    return int(user_id)
