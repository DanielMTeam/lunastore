# analytics domain data models & dtos for clickhouse events and reporting

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, ClassVar, Optional

from django.http import HttpRequest

from apps.analytics.extractors import extract_request_meta
from apps.analytics.reporting import optional_user_id


class AppEventType(StrEnum):
    VIEW = "view"
    DOWNLOAD = "download"
    LIKE = "like"
    UNLIKE = "unlike"
    RATE = "rate"
    ADD_TO_COLLECTION = "add_to_collection"
    EXTERNAL_LINK = "external_link"


class CollectionEventType(StrEnum):
    VIEW = "view"
    FAVORITE = "favorite"
    UNFAVORITE = "unfavorite"
    ADD_ITEM = "add_item"
    REMOVE_ITEM = "remove_item"
    SHARE = "share"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BaseAnalyticsEvent:
    event_time: datetime = field(default_factory=_utcnow)
    user_id: Optional[int] = None
    ip: str = ""
    country: str = ""
    os_name: str = ""
    browser: str = ""
    referer: str = ""
    session_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(data.get("event_time"), datetime):
            data["event_time"] = data["event_time"].isoformat()
        if "event_type" in data and hasattr(data["event_type"], "value"):
            data["event_type"] = data["event_type"].value
        return data

    def meta_json(self) -> str:
        if isinstance(self.meta, str):
            return self.meta[:4096]
        try:
            return json.dumps(self.meta or {}, ensure_ascii=False, default=str)[:4096]
        except Exception:
            return "{}"


@dataclass
class AppEvent(BaseAnalyticsEvent):
    app_id: int = 0
    event_type: str = AppEventType.VIEW
    distribution_id: Optional[int] = None
    category_id: Optional[int] = None
    os_version: str = ""

    TABLE_NAME: ClassVar[str] = "analytics_app_events"
    COLUMN_NAMES: ClassVar[list[str]] = [
        "event_time",
        "event_type",
        "app_id",
        "distribution_id",
        "category_id",
        "user_id",
        "ip",
        "country",
        "os_name",
        "os_version",
        "browser",
        "referer",
        "session_id",
        "meta",
    ]

    def to_clickhouse_row(self) -> list[Any]:
        evt_type = (
            self.event_type.value
            if isinstance(self.event_type, AppEventType)
            else str(self.event_type)
        )
        return [
            self.event_time or _utcnow(),
            evt_type,
            int(self.app_id),
            int(self.distribution_id) if self.distribution_id is not None else None,
            int(self.category_id) if self.category_id is not None else None,
            optional_user_id(self.user_id),
            str(self.ip or "")[:45],
            str(self.country or "")[:8],
            str(self.os_name or "")[:64],
            str(self.os_version or "")[:32],
            str(self.browser or "")[:64],
            str(self.referer or "")[:500],
            str(self.session_id or "")[:64],
            self.meta_json(),
        ]

    @classmethod
    def from_request(
        cls,
        request: Optional[HttpRequest],
        app_id: int,
        event_type: str | AppEventType = AppEventType.VIEW,
        *,
        distribution_id: Optional[int] = None,
        category_id: Optional[int] = None,
        meta: Optional[dict[str, Any]] = None,
        event_time: Optional[datetime] = None,
    ) -> AppEvent:
        req_meta = extract_request_meta(request)
        return cls(
            event_time=event_time or _utcnow(),
            event_type=event_type,
            app_id=int(app_id),
            distribution_id=distribution_id,
            category_id=category_id,
            user_id=req_meta["user_id"],
            ip=req_meta["ip"],
            country=req_meta["country"],
            os_name=req_meta["os_name"],
            os_version=req_meta["os_version"],
            browser=req_meta["browser"],
            referer=req_meta["referer"],
            session_id=req_meta["session_id"],
            meta=meta or {},
        )


@dataclass
class CollectionEvent(BaseAnalyticsEvent):
    collection_id: int = 0
    event_type: str = CollectionEventType.VIEW
    owner_id: Optional[int] = None
    app_id: Optional[int] = None
    is_system: bool = False
    is_public: bool = True

    TABLE_NAME: ClassVar[str] = "analytics_collection_events"
    COLUMN_NAMES: ClassVar[list[str]] = [
        "event_time",
        "event_type",
        "collection_id",
        "owner_id",
        "user_id",
        "app_id",
        "is_system",
        "is_public",
        "ip",
        "country",
        "os_name",
        "browser",
        "referer",
        "session_id",
        "meta",
    ]

    def to_clickhouse_row(self) -> list[Any]:
        evt_type = (
            self.event_type.value
            if isinstance(self.event_type, CollectionEventType)
            else str(self.event_type)
        )
        return [
            self.event_time or _utcnow(),
            evt_type,
            int(self.collection_id),
            int(self.owner_id) if self.owner_id is not None else None,
            optional_user_id(self.user_id),
            int(self.app_id) if self.app_id is not None else None,
            1 if self.is_system else 0,
            1 if self.is_public else 0,
            str(self.ip or "")[:45],
            str(self.country or "")[:8],
            str(self.os_name or "")[:64],
            str(self.browser or "")[:64],
            str(self.referer or "")[:500],
            str(self.session_id or "")[:64],
            self.meta_json(),
        ]

    @classmethod
    def from_request(
        cls,
        request: Optional[HttpRequest],
        collection_id: int,
        event_type: str | CollectionEventType = CollectionEventType.VIEW,
        *,
        owner_id: Optional[int] = None,
        app_id: Optional[int] = None,
        is_system: bool = False,
        is_public: bool = True,
        meta: Optional[dict[str, Any]] = None,
        event_time: Optional[datetime] = None,
    ) -> CollectionEvent:
        req_meta = extract_request_meta(request)
        return cls(
            event_time=event_time or _utcnow(),
            event_type=event_type,
            collection_id=int(collection_id),
            owner_id=owner_id,
            user_id=req_meta["user_id"],
            app_id=app_id,
            is_system=is_system,
            is_public=is_public,
            ip=req_meta["ip"],
            country=req_meta["country"],
            os_name=req_meta["os_name"],
            browser=req_meta["browser"],
            referer=req_meta["referer"],
            session_id=req_meta["session_id"],
            meta=meta or {},
        )


# reporting & metric dtos
@dataclass
class TimeseriesPoint:
    date: str
    count: int = 0


@dataclass
class BreakdownItem:
    name: str
    count: int = 0
    percentage: float = 0.0


@dataclass
class ChartBarItem:
    date: str
    val1: int
    val2: int
    height1: int  # percentage 0..100
    height2: int  # percentage 0..100
    short_date: str = ""


def _build_chart_bars(
    series1: list[TimeseriesPoint],
    series2: list[TimeseriesPoint],
    days: int = 14,
) -> list[ChartBarItem]:
    data1_by_date = {p.date: p.count for p in series1}
    data2_by_date = {p.date: p.count for p in series2}
    if not data1_by_date and not data2_by_date:
        return []

    # Generate contiguous date range for the specified number of days
    now = datetime.now(timezone.utc).date()
    all_dates = [(now - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    max_val = max(
        max(data1_by_date.values(), default=0),
        max(data2_by_date.values(), default=0),
    )
    if max_val <= 0:
        max_val = 1

    bars = []
    for d in all_dates:
        v1 = data1_by_date.get(d, 0)
        v2 = data2_by_date.get(d, 0)
        h1 = int(round((v1 / max_val) * 85)) if v1 > 0 else 0
        h2 = int(round((v2 / max_val) * 85)) if v2 > 0 else 0
        if v1 > 0 and h1 < 2:
            h1 = 2
        if v2 > 0 and h2 < 2:
            h2 = 2
        # short date e.g. "15.08" from "2026-08-15"
        parts = d.split("-")
        short_d = f"{parts[2]}.{parts[1]}" if len(parts) == 3 else d
        bars.append(
            ChartBarItem(
                date=d,
                val1=v1,
                val2=v2,
                height1=h1,
                height2=h2,
                short_date=short_d,
            )
        )
    return bars


@dataclass
class AppAnalyticsSummary:
    app_id: int
    days: int = 14
    total_views: int = 0
    total_downloads: int = 0
    total_likes: int = 0
    total_rates: int = 0
    unique_viewers: int = 0
    unique_downloaders: int = 0
    views_history: list[TimeseriesPoint] = field(default_factory=list)
    downloads_history: list[TimeseriesPoint] = field(default_factory=list)
    countries_breakdown: list[BreakdownItem] = field(default_factory=list)
    os_breakdown: list[BreakdownItem] = field(default_factory=list)
    distributions_breakdown: list[BreakdownItem] = field(default_factory=list)

    @property
    def has_chart_data(self) -> bool:
        return bool(self.views_history or self.downloads_history)

    @property
    def chart_bars(self) -> list[ChartBarItem]:
        return _build_chart_bars(self.views_history, self.downloads_history, days=self.days)


@dataclass
class CollectionAnalyticsSummary:
    collection_id: int
    days: int = 14
    total_views: int = 0
    total_favorites: int = 0
    total_item_adds: int = 0
    unique_viewers: int = 0
    views_history: list[TimeseriesPoint] = field(default_factory=list)
    favorites_history: list[TimeseriesPoint] = field(default_factory=list)
    countries_breakdown: list[BreakdownItem] = field(default_factory=list)

    @property
    def has_chart_data(self) -> bool:
        return bool(self.views_history or self.favorites_history)

    @property
    def chart_bars(self) -> list[ChartBarItem]:
        return _build_chart_bars(self.views_history, self.favorites_history, days=self.days)
