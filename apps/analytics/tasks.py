# django.tasks helpers for clickhouse inserts

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from django.tasks import task

from apps.analytics.reporting import (
    AnalyticsUnavailableError,
    report_analytics_error,
)

logger = logging.getLogger("analytics")


@task()
def insert_table_rows_task(
    table: str,
    data: Sequence[Sequence[Any]],
    column_names: Sequence[str],
) -> None:
    # generic async insert of rows into any clickhouse table
    from apps.analytics.client import get_analytics_client
    from apps.analytics.services import is_enabled

    if not is_enabled():
        logger.debug(
            "insert_table_rows_task skipped: disabled table=%s",
            table,
        )
        return

    if not data:
        return

    try:
        client = get_analytics_client(force_enabled=True)
        client.insert_rows(table, data, column_names)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"insert_table_rows_task failed table={table} count={len(data)}",
        )
        if isinstance(exc, AnalyticsUnavailableError):
            raise
        raise AnalyticsUnavailableError(
            f"insert_table_rows_task failed table={table} count={len(data)}"
        ) from exc


@task()
def insert_app_event_task(
    row: Sequence[Any],
) -> None:
    # insert single app event row into analytics_app_events
    from apps.analytics.models import AppEvent

    insert_table_rows_task(AppEvent.TABLE_NAME, [row], AppEvent.COLUMN_NAMES)


@task()
def insert_collection_event_task(
    row: Sequence[Any],
) -> None:
    # insert single collection event row into analytics_collection_events
    from apps.analytics.models import CollectionEvent

    insert_table_rows_task(
        CollectionEvent.TABLE_NAME,
        [row],
        CollectionEvent.COLUMN_NAMES,
    )


@task()
def insert_analytics_event(
    event_name: str,
    user_id: Optional[int] = None,
    event_time_iso: Optional[str] = None,
    properties: Optional[Mapping[str, Any]] = None,
) -> None:
    # legacy raw event → clickhouse
    from apps.analytics.client import get_analytics_client
    from apps.analytics.services import is_enabled

    if not is_enabled():
        logger.debug("insert_analytics_event skipped: disabled")
        return

    event_time: Optional[datetime] = None
    if event_time_iso:
        try:
            event_time = datetime.fromisoformat(event_time_iso)
        except ValueError:
            logger.warning("invalid event_time_iso=%s", event_time_iso)

    try:
        client = get_analytics_client(force_enabled=True)
        client.insert_event(
            event_name,
            user_id=user_id,
            event_time=event_time,
            properties=properties,
        )
    except Exception as exc:
        report_analytics_error(
            exc,
            f"insert_analytics_event failed name={event_name}",
        )
        if isinstance(exc, AnalyticsUnavailableError):
            raise
        raise AnalyticsUnavailableError(
            f"insert_analytics_event failed name={event_name}"
        ) from exc


@task()
def insert_analytics_events_batch(
    rows: Sequence[Mapping[str, Any]],
) -> None:
    # legacy batch of raw events → clickhouse
    from apps.analytics.client import get_analytics_client
    from apps.analytics.services import is_enabled

    if not is_enabled():
        logger.debug("insert_analytics_events_batch skipped: disabled")
        return

    if not rows:
        return

    try:
        client = get_analytics_client(force_enabled=True)
        client.insert_events_batch(rows)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"insert_analytics_events_batch failed count={len(rows)}",
        )
        if isinstance(exc, AnalyticsUnavailableError):
            raise
        raise AnalyticsUnavailableError(
            f"insert_analytics_events_batch failed count={len(rows)}"
        ) from exc
