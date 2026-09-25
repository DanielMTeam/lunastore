# batch flusher from redis buffer into clickhouse

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional, Sequence

from django.core.cache import cache

from apps.analytics.buffer import get_buffer_key, get_redis_client, pop_buffer_batch
from apps.analytics.config import get_circuit_breaker_timeout, get_flush_batch_size
from apps.analytics.reporting import report_analytics_error

logger = logging.getLogger("analytics")

CIRCUIT_BREAKER_KEY = "analytics:circuit_open"
CIRCUIT_BREAKER_TIMEOUT = 30  # seconds fallback


def is_circuit_open() -> bool:
    try:
        return bool(cache.get(CIRCUIT_BREAKER_KEY))
    except Exception:
        return False


def record_circuit_failure(timeout: Optional[int] = None) -> None:
    try:
        t = timeout if timeout is not None else get_circuit_breaker_timeout()
        cache.set(CIRCUIT_BREAKER_KEY, 1, timeout=t)
    except Exception:
        pass


def record_circuit_success() -> None:
    try:
        cache.delete(CIRCUIT_BREAKER_KEY)
    except Exception:
        pass


def _resolve_table_columns(table_name: str) -> list[str]:
    from apps.analytics.models import AppEvent, CollectionEvent

    if table_name == AppEvent.TABLE_NAME:
        return list(AppEvent.COLUMN_NAMES)
    elif table_name == CollectionEvent.TABLE_NAME:
        return list(CollectionEvent.COLUMN_NAMES)
    elif table_name == "analytics_events":
        return ["event_name", "user_id", "event_time", "properties"]
    return []


def _format_batch_rows(rows: Sequence[Sequence[Any]]) -> list[list[Any]]:
    formatted: list[list[Any]] = []
    for row in rows:
        row_list = list(row)
        if row_list and isinstance(row_list[0], str):
            try:
                row_list[0] = datetime.fromisoformat(row_list[0])
            except Exception:
                pass
        formatted.append(row_list)
    return formatted


def _requeue_unwritten_rows(table_name: str, rows: Sequence[Sequence[Any]]) -> None:
    # prepend unwritten rows back to buffer in original order
    if not rows:
        return
    redis_client = get_redis_client()
    if redis_client is not None:
        key = get_buffer_key(table_name)
        try:
            serialized_rows = [
                json.dumps(r, ensure_ascii=False, default=str)
                for r in reversed(rows)
            ]
            redis_client.lpush(key, *serialized_rows)
        except Exception as exc:
            logger.error("failed to requeue unwritten rows to redis for table=%s: %s", table_name, exc)
    else:
        from apps.analytics.buffer import _memory_buffers

        serialized_rows = [
            json.dumps(r, ensure_ascii=False, default=str)
            for r in rows
        ]
        _memory_buffers[table_name] = serialized_rows + _memory_buffers[table_name]


def flush_table_buffer(
    table_name: str,
    batch_size: Optional[int] = None,
    client: Optional[Any] = None,
) -> int:
    # pop a batch of events from buffer and insert into clickhouse in bulk
    from apps.analytics.client import get_analytics_client
    from apps.analytics.services import is_enabled

    if not is_enabled():
        return 0

    if is_circuit_open():
        logger.debug("flush_table_buffer skipped: circuit breaker open table=%s", table_name)
        return 0

    if batch_size is None:
        batch_size = get_flush_batch_size()

    rows = pop_buffer_batch(table_name, batch_size=batch_size)
    if not rows:
        return 0

    column_names = _resolve_table_columns(table_name)
    if not column_names:
        logger.error("unknown table columns for table=%s, dropping batch of %d rows", table_name, len(rows))
        return 0

    formatted_rows = _format_batch_rows(rows)

    if client is None:
        try:
            client = get_analytics_client(force_enabled=True)
        except Exception as exc:
            report_analytics_error(exc, f"client unavailable for flush table={table_name}")
            record_circuit_failure()
            _requeue_unwritten_rows(table_name, rows)
            return 0

    try:
        client.insert_rows(
            table_name,
            formatted_rows,
            column_names,
            wait_for_async_insert=0,
        )
        record_circuit_success()
        try:
            cache.delete(f"analytics:flusher:fails:{table_name}")
        except Exception:
            pass
        logger.debug("flushed %d rows to table=%s", len(formatted_rows), table_name)
        return len(formatted_rows)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"flush_table_buffer failed table={table_name} count={len(rows)}",
        )
        record_circuit_failure()

        # drop non-retryable errors or repeated failures
        is_non_retryable = type(exc).__name__ in (
            "DataError",
            "ProgrammingError",
            "IntegrityError",
            "NotSupportedError",
        )

        fail_key = f"analytics:flusher:fails:{table_name}"
        try:
            fails = cache.incr(fail_key)
        except Exception:
            fails = 1
            try:
                cache.set(fail_key, 1, timeout=300)
            except Exception:
                pass

        if is_non_retryable or fails > 5:
            logger.critical(
                "dropping unwritten batch of %d rows for table=%s to prevent queue freeze (non_retryable=%s fails=%d): %s",
                len(rows),
                table_name,
                is_non_retryable,
                fails,
                exc,
            )
        else:
            _requeue_unwritten_rows(table_name, rows)
        return 0


def flush_all_analytics_buffers(
    batch_size: Optional[int] = None,
    client: Optional[Any] = None,
) -> dict[str, int]:
    # drain all buffers up to batch_size per table
    from apps.analytics.models import AppEvent, CollectionEvent

    if batch_size is None:
        batch_size = get_flush_batch_size()

    tables = [AppEvent.TABLE_NAME, CollectionEvent.TABLE_NAME, "analytics_events"]
    result: dict[str, int] = {}

    for table in tables:
        result[table] = flush_table_buffer(table, batch_size=batch_size, client=client)

    return result
