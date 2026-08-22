# clickhouse client factory + null fallback when analytics is off

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Mapping, Optional, Protocol, Sequence

from django.conf import settings

from apps.analytics.reporting import (
    AnalyticsUnavailableError,
    optional_user_id,
)

if TYPE_CHECKING:
    from apps.analytics.models import AppEvent, CollectionEvent

logger = logging.getLogger("analytics")

_client_lock = threading.Lock()
_shared_client: Optional["ClickHouseAnalyticsClient"] = None


class AnalyticsClient(Protocol):
    # shared client shape for services/tasks

    def ping(self) -> bool:
        ...

    def insert_event(
        self,
        event_name: str,
        *,
        user_id: Optional[int] = None,
        event_time: Optional[datetime] = None,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        ...

    def insert_events_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> None:
        ...

    def insert_rows(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: Sequence[str],
    ) -> None:
        ...

    def query_rows(
        self,
        query: str,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> list[Sequence[Any]]:
        ...

    def insert_app_events(
        self,
        events: Sequence[AppEvent],
    ) -> None:
        ...

    def insert_collection_events(
        self,
        events: Sequence[CollectionEvent],
    ) -> None:
        ...

    def execute(self, query: str) -> Any:
        ...

    def close(self) -> None:
        ...


class NullAnalyticsClient:
    # does nothing — used only when analytics is off

    def ping(self) -> bool:
        return False

    def insert_event(
        self,
        event_name: str,
        *,
        user_id: Optional[int] = None,
        event_time: Optional[datetime] = None,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        logger.debug(
            "null client skipped insert_event name=%s user_id=%s",
            event_name,
            user_id,
        )

    def insert_events_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> None:
        logger.debug(
            "null client skipped insert_events_batch count=%s",
            len(rows),
        )

    def insert_rows(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: Sequence[str],
    ) -> None:
        logger.debug(
            "null client skipped insert_rows table=%s count=%s",
            table,
            len(data),
        )

    def query_rows(
        self,
        query: str,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> list[Sequence[Any]]:
        logger.debug("null client skipped query_rows query=%s", query[:120])
        return []

    def insert_app_events(
        self,
        events: Sequence[AppEvent],
    ) -> None:
        logger.debug(
            "null client skipped insert_app_events count=%s",
            len(events),
        )

    def insert_collection_events(
        self,
        events: Sequence[CollectionEvent],
    ) -> None:
        logger.debug(
            "null client skipped insert_collection_events count=%s",
            len(events),
        )

    def execute(self, query: str) -> Any:
        logger.debug("null client skipped execute query=%s", query[:120])
        return None

    def close(self) -> None:
        return None


class ClickHouseAnalyticsClient:
    # thin wrapper around clickhouse-connect (shared by default)

    def __init__(self, client: Any, *, shared: bool = True) -> None:
        self._client = client
        self._shared = shared

    def ping(self) -> bool:
        try:
            result = self._client.query("SELECT 1")
            return bool(result.result_rows)
        except Exception:
            logger.exception("clickhouse ping failed")
            return False

    def insert_event(
        self,
        event_name: str,
        *,
        user_id: Optional[int] = None,
        event_time: Optional[datetime] = None,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        row = {
            "event_name": event_name,
            "user_id": optional_user_id(user_id),
            "event_time": event_time or datetime.now(timezone.utc),
            "properties": json.dumps(properties or {}, ensure_ascii=False),
        }
        self.insert_events_batch([row])

    def insert_events_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> None:
        if not rows:
            return
        column_names = ["event_name", "user_id", "event_time", "properties"]
        data = [
            [
                row.get("event_name", ""),
                optional_user_id(
                    row["user_id"] if "user_id" in row else None
                ),
                row.get("event_time") or datetime.now(timezone.utc),
                (
                    row.get("properties")
                    if isinstance(row.get("properties"), str)
                    else json.dumps(
                        row.get("properties") or {},
                        ensure_ascii=False,
                    )
                ),
            ]
            for row in rows
        ]
        self.insert_rows("analytics_events", data, column_names)

    def insert_rows(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: Sequence[str],
    ) -> None:
        if not data:
            return
        try:
            self._client.insert(
                table,
                data,
                column_names=list(column_names),
                settings={
                    "async_insert": 1,
                    # wait until server accepted the insert
                    "wait_for_async_insert": 1,
                },
            )
        except Exception:
            logger.exception(
                "clickhouse insert_rows failed table=%s count=%s",
                table,
                len(data),
            )
            raise

    def query_rows(
        self,
        query: str,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> list[Sequence[Any]]:
        try:
            result = self._client.query(
                query,
                parameters=dict(parameters or {}),
            )
            return list(result.result_rows or [])
        except Exception:
            logger.exception("clickhouse query_rows failed")
            raise

    def insert_app_events(
        self,
        events: Sequence[AppEvent],
    ) -> None:
        if not events:
            return
        from apps.analytics.models import AppEvent

        data = [e.to_clickhouse_row() for e in events]
        self.insert_rows(AppEvent.TABLE_NAME, data, AppEvent.COLUMN_NAMES)

    def insert_collection_events(
        self,
        events: Sequence[CollectionEvent],
    ) -> None:
        if not events:
            return
        from apps.analytics.models import CollectionEvent

        data = [e.to_clickhouse_row() for e in events]
        self.insert_rows(
            CollectionEvent.TABLE_NAME,
            data,
            CollectionEvent.COLUMN_NAMES,
        )

    def execute(self, query: str) -> Any:
        try:
            return self._client.command(query)
        except Exception:
            logger.exception("clickhouse execute failed")
            raise

    def close(self) -> None:
        # shared client stays open; use reset_analytics_client() to drop it
        if self._shared:
            return
        self._dispose()

    def _dispose(self) -> None:
        try:
            self._client.close()
        except Exception:
            logger.exception("clickhouse client close failed")


def reset_analytics_client() -> None:
    # drop cached connection (tests / reconnect)
    global _shared_client
    with _client_lock:
        if _shared_client is not None:
            _shared_client._dispose()
            _shared_client = None


def get_analytics_client(*, force_enabled: bool = False) -> AnalyticsClient:
    # Reusing a thread-safe long-lived client shares the underlying urllib3 HTTP connection pool,
    # avoiding TCP/TLS handshake and auth overhead on every analytics operation while
    # taking full advantage of ClickHouse async_insert batching
    from apps.analytics.services import is_enabled

    if not force_enabled and not is_enabled():
        return NullAnalyticsClient()

    global _shared_client
    with _client_lock:
        if _shared_client is not None:
            return _shared_client

        try:
            import clickhouse_connect
        except ImportError as exc:
            logger.exception("clickhouse-connect is not installed")
            raise AnalyticsUnavailableError(
                "clickhouse-connect is not installed"
            ) from exc

        try:
            raw = clickhouse_connect.get_client(
                host=getattr(settings, "CLICKHOUSE_HOST", "clickhouse"),
                port=int(getattr(settings, "CLICKHOUSE_PORT", 8123)),
                username=getattr(settings, "CLICKHOUSE_USER", "analytics"),
                password=getattr(settings, "CLICKHOUSE_PASSWORD", ""),
                database=getattr(
                    settings,
                    "CLICKHOUSE_DATABASE",
                    "lunastore_analytics",
                ),
                secure=bool(getattr(settings, "CLICKHOUSE_SECURE", False)),
            )
            _shared_client = ClickHouseAnalyticsClient(raw, shared=True)
            return _shared_client
        except AnalyticsUnavailableError:
            raise
        except Exception as exc:
            logger.exception("failed to create clickhouse client")
            raise AnalyticsUnavailableError(
                "failed to create clickhouse client"
            ) from exc
