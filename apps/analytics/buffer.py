# redis-backed buffering for clickhouse event telemetry

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict
from typing import Any, Mapping, Optional, Sequence

from django.conf import settings

from apps.analytics.config import get_buffer_max_size, get_flush_batch_size, get_flush_threshold

logger = logging.getLogger("analytics")

BUFFER_KEY_PREFIX = "analytics:buffer:"
MAX_BUFFER_SIZE = 100_000
FLUSH_THRESHOLD = 500
MAX_EVENT_PAYLOAD_BYTES = 65_536  # 64 KB per event maximum

_TABLE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{1,64}$")


def is_valid_table_name(table_name: str) -> bool:
    if not table_name or not isinstance(table_name, str):
        return False
    return bool(_TABLE_NAME_REGEX.match(table_name))


_memory_buffers: dict[str, list[str]] = defaultdict(list)
_use_memory_fallback: bool = False
_direct_redis_client: Any = None
_direct_redis_lock = threading.Lock()
_last_direct_redis_fail_time: float = 0.0


def set_memory_fallback(enabled: bool) -> None:
    # force in-memory mode (useful for unit tests without redis)
    global _use_memory_fallback
    _use_memory_fallback = enabled


def clear_memory_buffers() -> None:
    # reset in-memory buffers
    _memory_buffers.clear()


def get_buffer_key(table_name: str) -> str:
    return f"{BUFFER_KEY_PREFIX}{table_name}"


def get_redis_client() -> Any:
    if _use_memory_fallback:
        return None

    # django-redis cache backend
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception:
        pass

    # direct redis connection with fallback pool
    global _direct_redis_client, _last_direct_redis_fail_time
    if _direct_redis_client is not None:
        return _direct_redis_client

    if time.time() - _last_direct_redis_fail_time < 10.0:
        return None

    with _direct_redis_lock:
        if _direct_redis_client is not None:
            return _direct_redis_client
        if time.time() - _last_direct_redis_fail_time < 10.0:
            return None
        try:
            import redis

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            client = redis.Redis.from_url(
                redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            client.ping()
            _direct_redis_client = client
            return _direct_redis_client
        except Exception:
            _last_direct_redis_fail_time = time.time()
            return None


def push_event_to_buffer(table_name: str, row: Sequence[Any]) -> bool:
    # serialize row to json and append to redis buffer (fail-silent)
    if not is_valid_table_name(table_name) or not row:
        return False

    try:
        payload = json.dumps(list(row), ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("failed to serialize event row for table=%s: %s", table_name, exc)
        return False

    if len(payload) > MAX_EVENT_PAYLOAD_BYTES:
        logger.warning("event payload exceeds max allowed size (%d bytes) for table=%s", len(payload), table_name)
        return False

    max_size = get_buffer_max_size()
    redis_client = get_redis_client()
    if redis_client is not None:
        key = get_buffer_key(table_name)
        try:
            pipe = redis_client.pipeline(transaction=False)
            # drain transient in-memory events if redis recovered
            if _memory_buffers.get(table_name):
                mem_items = _memory_buffers.pop(table_name, [])
                if mem_items:
                    pipe.rpush(key, *mem_items)

            pipe.rpush(key, payload)
            pipe.llen(key)
            results = pipe.execute()
            buffer_len = results[-1] if results else 0

            # enforce max buffer size to prevent memory exhaustion
            if buffer_len > max_size:
                redis_client.ltrim(key, buffer_len - max_size, -1)
            return True
        except Exception as exc:
            logger.warning("redis push_event_to_buffer failed for table=%s: %s", table_name, exc)
            # fallback to in-memory on redis failure
            _memory_buffers[table_name].append(payload)
            if len(_memory_buffers[table_name]) > max_size:
                _memory_buffers[table_name] = _memory_buffers[table_name][-max_size:]
            return True
    else:
        # in-memory buffer fallback
        _memory_buffers[table_name].append(payload)
        if len(_memory_buffers[table_name]) > max_size:
            _memory_buffers[table_name] = _memory_buffers[table_name][-max_size:]
        return True


def pop_buffer_batch(table_name: str, batch_size: Optional[int] = None) -> list[list[Any]]:
    # atomically pop up to batch_size rows from buffer
    if not is_valid_table_name(table_name):
        return []

    if batch_size is None:
        batch_size = get_flush_batch_size()
    try:
        batch_size = int(batch_size)
    except (ValueError, TypeError):
        batch_size = get_flush_batch_size()

    if batch_size <= 0:
        return []

    raw_items: list[str] = []
    redis_client = get_redis_client()

    if redis_client is not None:
        key = get_buffer_key(table_name)
        # drain residual memory buffer if any
        if _memory_buffers.get(table_name):
            try:
                residual = _memory_buffers.pop(table_name, [])
                if residual:
                    redis_client.rpush(key, *residual)
            except Exception:
                pass

        try:
            popped = redis_client.lpop(key, count=batch_size)
            if popped:
                if isinstance(popped, (bytes, str)):
                    popped = [popped]
                raw_items = [
                    item.decode("utf-8") if isinstance(item, bytes) else str(item)
                    for item in popped
                ]
        except Exception as exc:
            logger.warning("redis lpop failed for table=%s: %s", table_name, exc)
    else:
        # in-memory buffer pop
        mem_list = _memory_buffers.get(table_name, [])
        raw_items = mem_list[:batch_size]
        _memory_buffers[table_name] = mem_list[batch_size:]

    result_rows: list[list[Any]] = []
    for item in raw_items:
        try:
            row = json.loads(item)
            if isinstance(row, list):
                result_rows.append(row)
        except Exception as exc:
            logger.warning("failed to decode buffered row for table=%s: %s", table_name, exc)

    return result_rows


def get_buffer_length(table_name: str) -> int:
    # return number of events currently waiting in buffer
    if not is_valid_table_name(table_name):
        return 0

    redis_client = get_redis_client()
    if redis_client is not None:
        key = get_buffer_key(table_name)
        try:
            return int(redis_client.llen(key))
        except Exception as exc:
            logger.debug("get_buffer_length failed for table=%s: %s", table_name, exc)
            return len(_memory_buffers.get(table_name, []))
    return len(_memory_buffers.get(table_name, []))


def get_all_buffer_lengths() -> dict[str, int]:
    # return pending count for known analytics tables
    from apps.analytics.models import AppEvent, CollectionEvent

    tables = [AppEvent.TABLE_NAME, CollectionEvent.TABLE_NAME, "analytics_events"]
    return {tbl: get_buffer_length(tbl) for tbl in tables}


def clear_buffer(table_name: str) -> None:
    # delete buffer for table (useful for tests and cleanup)
    if not is_valid_table_name(table_name):
        return

    redis_client = get_redis_client()
    if redis_client is not None:
        key = get_buffer_key(table_name)
        try:
            redis_client.delete(key)
        except Exception as exc:
            logger.debug("clear_buffer failed for table=%s: %s", table_name, exc)
    _memory_buffers.pop(table_name, None)
