# public analytics api for tracking and reporting

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from django.http import HttpRequest

from apps.analytics.models import (
    AppAnalyticsSummary,
    AppEvent,
    AppEventType,
    BreakdownItem,
    CollectionAnalyticsSummary,
    CollectionEvent,
    CollectionEventType,
    TimeseriesPoint,
)
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


#
# deduplication & cooldown helpers
#


def _get_actor_key(request: Optional[HttpRequest]) -> str:
    # return unique actor key (user ID, session ID, or client IP)
    if request is None:
        return ""
    try:
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return f"u:{user.pk}"
        session = getattr(request, "session", None)
        if session and getattr(session, "session_key", None):
            return f"s:{session.session_key}"
        from apps.core.utils import get_client_ip

        ip = get_client_ip(request)
        if ip:
            return f"ip:{ip}"
    except Exception:
        logger.debug("failed to resolve actor key", exc_info=True)
    return ""


def _is_event_deduplicated(dedup_key: str, timeout: int) -> bool:
    # returns True if event was recently recorded and should be ignored
    if not dedup_key or timeout <= 0:
        return False
    try:
        from django.core.cache import cache

        was_added = cache.add(dedup_key, 1, timeout=timeout)
        return not was_added
    except Exception:
        logger.debug("deduplication cache check failed key=%s", dedup_key, exc_info=True)
        return False


#
# application tracking api
#


def track_app_event(event: AppEvent) -> None:
    # enqueue app event insert via django.tasks; no-op when analytics is off
    if not is_enabled():
        logger.debug("track_app_event skipped: disabled")
        return

    from apps.analytics.tasks import insert_app_event_task

    try:
        row = list(event.to_clickhouse_row())
        if hasattr(row[0], "isoformat"):
            row[0] = row[0].isoformat()
        insert_app_event_task.enqueue(row)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to enqueue app event app_id={event.app_id} type={event.event_type}",
        )


def track_app_view(
    request: Optional[HttpRequest],
    app_id: int,
    *,
    category_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
    deduplicate: bool = True,
    dedup_timeout: int = 1800,
) -> None:
    if not is_enabled() or not app_id:
        return

    if deduplicate and request is not None:
        actor = _get_actor_key(request)
        if actor:
            key = f"analytics:dedup:app_v:{app_id}:{actor}"
            if _is_event_deduplicated(key, dedup_timeout):
                logger.debug("track_app_view skipped by dedup key=%s", key)
                return

    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=AppEventType.VIEW,
            category_id=category_id,
            meta=meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=AppEventType.VIEW,
            category_id=category_id,
            meta=meta or {},
        )
    track_app_event(event)


def track_app_download(
    request: Optional[HttpRequest],
    app_id: int,
    *,
    distribution_id: Optional[int] = None,
    category_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
    deduplicate: bool = True,
    dedup_timeout: int = 600,
) -> None:
    if not is_enabled() or not app_id:
        return

    if deduplicate and request is not None:
        actor = _get_actor_key(request)
        if actor:
            key = f"analytics:dedup:dl:{app_id}:{distribution_id or 0}:{actor}"
            if _is_event_deduplicated(key, dedup_timeout):
                logger.debug("track_app_download skipped by dedup key=%s", key)
                return

    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=AppEventType.DOWNLOAD,
            distribution_id=distribution_id,
            category_id=category_id,
            meta=meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=AppEventType.DOWNLOAD,
            distribution_id=distribution_id,
            category_id=category_id,
            meta=meta or {},
        )
    track_app_event(event)


def track_app_like(
    request: Optional[HttpRequest],
    app_id: int,
    is_like: bool = True,
    *,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not app_id:
        return
    evt_type = AppEventType.LIKE if is_like else AppEventType.UNLIKE
    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=evt_type,
            meta=meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=evt_type,
            meta=meta or {},
        )
    track_app_event(event)


def track_app_rate(
    request: Optional[HttpRequest],
    app_id: int,
    *,
    rating: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not app_id:
        return
    combined_meta = dict(meta or {})
    if rating is not None:
        combined_meta["rating"] = int(rating)
    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=AppEventType.RATE,
            meta=combined_meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=AppEventType.RATE,
            meta=combined_meta,
        )
    track_app_event(event)


def track_app_collection_add(
    request: Optional[HttpRequest],
    app_id: int,
    *,
    collection_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not app_id:
        return
    combined_meta = dict(meta or {})
    if collection_id is not None:
        combined_meta["collection_id"] = int(collection_id)
    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=AppEventType.ADD_TO_COLLECTION,
            meta=combined_meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=AppEventType.ADD_TO_COLLECTION,
            meta=combined_meta,
        )
    track_app_event(event)


def track_app_collection_remove(
    request: Optional[HttpRequest],
    app_id: int,
    *,
    collection_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not app_id:
        return
    combined_meta = dict(meta or {})
    if collection_id is not None:
        combined_meta["collection_id"] = int(collection_id)
    if request is not None:
        event = AppEvent.from_request(
            request,
            app_id,
            event_type=AppEventType.REMOVE_FROM_COLLECTION,
            meta=combined_meta,
        )
    else:
        event = AppEvent(
            app_id=int(app_id),
            event_type=AppEventType.REMOVE_FROM_COLLECTION,
            meta=combined_meta,
        )
    track_app_event(event)


#
# collection tracking api
#


def track_collection_event(event: CollectionEvent) -> None:
    # enqueue collection event insert via django.tasks; no-op when analytics is off
    if not is_enabled():
        logger.debug("track_collection_event skipped: disabled")
        return

    from apps.analytics.tasks import insert_collection_event_task

    try:
        row = list(event.to_clickhouse_row())
        if hasattr(row[0], "isoformat"):
            row[0] = row[0].isoformat()
        insert_collection_event_task.enqueue(row)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to enqueue collection event collection_id={event.collection_id} type={event.event_type}",
        )


def track_collection_view(
    request: Optional[HttpRequest],
    collection_id: int,
    *,
    owner_id: Optional[int] = None,
    is_system: bool = False,
    is_public: bool = True,
    meta: Optional[dict[str, Any]] = None,
    deduplicate: bool = True,
    dedup_timeout: int = 1800,
) -> None:
    if not is_enabled() or not collection_id:
        return

    if deduplicate and request is not None:
        actor = _get_actor_key(request)
        if actor:
            key = f"analytics:dedup:col_v:{collection_id}:{actor}"
            if _is_event_deduplicated(key, dedup_timeout):
                logger.debug("track_collection_view skipped by dedup key=%s", key)
                return

    if request is not None:
        event = CollectionEvent.from_request(
            request,
            collection_id,
            event_type=CollectionEventType.VIEW,
            owner_id=owner_id,
            is_system=is_system,
            is_public=is_public,
            meta=meta,
        )
    else:
        event = CollectionEvent(
            collection_id=int(collection_id),
            event_type=CollectionEventType.VIEW,
            owner_id=owner_id,
            is_system=is_system,
            is_public=is_public,
            meta=meta or {},
        )
    track_collection_event(event)


def track_collection_favorite(
    request: Optional[HttpRequest],
    collection_id: int,
    is_favorite: bool = True,
    *,
    owner_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not collection_id:
        return
    evt_type = (
        CollectionEventType.FAVORITE
        if is_favorite
        else CollectionEventType.UNFAVORITE
    )
    if request is not None:
        event = CollectionEvent.from_request(
            request,
            collection_id,
            event_type=evt_type,
            owner_id=owner_id,
            meta=meta,
        )
    else:
        event = CollectionEvent(
            collection_id=int(collection_id),
            event_type=evt_type,
            owner_id=owner_id,
            meta=meta or {},
        )
    track_collection_event(event)


def track_collection_item_change(
    request: Optional[HttpRequest],
    collection_id: int,
    app_id: int,
    is_added: bool = True,
    *,
    owner_id: Optional[int] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    if not is_enabled() or not collection_id or not app_id:
        return
    evt_type = (
        CollectionEventType.ADD_ITEM
        if is_added
        else CollectionEventType.REMOVE_ITEM
    )
    if request is not None:
        event = CollectionEvent.from_request(
            request,
            collection_id,
            event_type=evt_type,
            owner_id=owner_id,
            app_id=app_id,
            meta=meta,
        )
    else:
        event = CollectionEvent(
            collection_id=int(collection_id),
            event_type=evt_type,
            owner_id=owner_id,
            app_id=app_id,
            meta=meta or {},
        )
    track_collection_event(event)


#
# legacy raw event api
#


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


#
# analytical reporting & query helpers (parameterized SQL)
#


def get_app_analytics(
    app_id: int,
    days: int = 30,
    chart_days: int = 14,
) -> AppAnalyticsSummary:
    # fetch aggregated analytics summary for a given app (chart over chart_days, tables over days)
    summary = AppAnalyticsSummary(app_id=int(app_id), days=int(chart_days))
    if not is_enabled() or not app_id:
        try:
            from apps.marketplace.models import Review
            summary.total_rates = Review.objects.filter(application_id=app_id).count()
        except Exception:
            pass
        return summary

    from apps.analytics.client import get_analytics_client

    try:
        client = get_analytics_client(force_enabled=True)
    except Exception as exc:
        report_analytics_error(exc, "get_app_analytics client unavailable")
        try:
            from apps.marketplace.models import Review
            summary.total_rates = Review.objects.filter(application_id=app_id).count()
        except Exception:
            pass
        return summary

    totals_params = {"app_id": int(app_id), "days": int(days)}
    chart_params = {"app_id": int(app_id), "days": int(chart_days)}

    # 1. Total counts & unique counts (30 days)
    try:
        totals_query = """
            SELECT
                countIf(event_type = 'view') AS views,
                countIf(event_type = 'download') AS downloads,
                countIf(event_type = 'like') AS likes,
                countIf(event_type = 'rate') AS rates,
                uniqIf(if(user_id IS NOT NULL, toString(user_id), ip), event_type = 'view') AS unique_viewers,
                uniqIf(if(user_id IS NOT NULL, toString(user_id), ip), event_type = 'download') AS unique_downloaders
            FROM analytics_app_events
            WHERE app_id = %(app_id)s
              AND event_time >= now() - toIntervalDay(%(days)s)
        """
        totals_rows = client.query_rows(totals_query, totals_params)
        if totals_rows:
            row = totals_rows[0]
            summary.total_views = int(row[0] or 0)
            summary.total_downloads = int(row[1] or 0)
            summary.total_likes = int(row[2] or 0)
            summary.total_rates = int(row[3] or 0)
            summary.unique_viewers = int(row[4] or 0)
            summary.unique_downloaders = int(row[5] or 0)
    except Exception as exc:
        report_analytics_error(exc, f"failed to query totals for app_id={app_id}")

    # 2. Daily timeseries (views and downloads over chart_days = 14 days)
    try:
        ts_query = """
            SELECT
                toDate(event_time) AS dt,
                countIf(event_type = 'view') AS views_cnt,
                countIf(event_type = 'download') AS downloads_cnt
            FROM analytics_app_events
            WHERE app_id = %(app_id)s
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY dt
            ORDER BY dt ASC
        """
        for r in client.query_rows(ts_query, chart_params):
            d_str = str(r[0])
            summary.views_history.append(TimeseriesPoint(date=d_str, count=int(r[1] or 0)))
            summary.downloads_history.append(TimeseriesPoint(date=d_str, count=int(r[2] or 0)))
    except Exception as exc:
        report_analytics_error(exc, f"failed to query timeseries for app_id={app_id}")

    # 3. Countries breakdown (30 days)
    try:
        country_query = """
            SELECT
                if(country = '' OR country IS NULL, 'Unknown', country) AS c,
                count() AS cnt
            FROM analytics_app_events
            WHERE app_id = %(app_id)s
              AND event_type = 'view'
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY c
            ORDER BY cnt DESC
            LIMIT 10
        """
        country_rows = client.query_rows(country_query, totals_params)
        total_c = sum(int(r[1]) for r in country_rows) or 1
        summary.countries_breakdown = [
            BreakdownItem(
                name=str(r[0]),
                count=int(r[1]),
                percentage=round((int(r[1]) / total_c) * 100, 1),
            )
            for r in country_rows
        ]
    except Exception as exc:
        report_analytics_error(exc, f"failed to query countries for app_id={app_id}")

    # 4. OS breakdown (30 days)
    try:
        os_query = """
            SELECT
                if(os_name = '' OR os_name IS NULL, 'Unknown', os_name) AS os,
                count() AS cnt
            FROM analytics_app_events
            WHERE app_id = %(app_id)s
              AND event_type = 'view'
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY os
            ORDER BY cnt DESC
            LIMIT 10
        """
        os_rows = client.query_rows(os_query, totals_params)
        total_os = sum(int(r[1]) for r in os_rows) or 1
        summary.os_breakdown = [
            BreakdownItem(
                name=str(r[0]),
                count=int(r[1]),
                percentage=round((int(r[1]) / total_os) * 100, 1),
            )
            for r in os_rows
        ]
    except Exception as exc:
        report_analytics_error(exc, f"failed to query OS for app_id={app_id}")

    # 5. Distributions breakdown (30 days)
    try:
        dist_query = """
            SELECT
                if(distribution_id IS NULL, 0, distribution_id) AS dist_id,
                count() AS cnt
            FROM analytics_app_events
            WHERE app_id = %(app_id)s
              AND event_type = 'download'
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY dist_id
            ORDER BY cnt DESC
            LIMIT 10
        """
        dist_rows = client.query_rows(dist_query, totals_params)
        total_d = sum(int(r[1]) for r in dist_rows) or 1
        summary.distributions_breakdown = [
            BreakdownItem(
                name=str(r[0]),
                count=int(r[1]),
                percentage=round((int(r[1]) / total_d) * 100, 1),
            )
            for r in dist_rows
        ]
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to query distributions for app_id={app_id}",
        )

    return summary


def get_collection_analytics(
    collection_id: int,
    days: int = 30,
    chart_days: int = 14,
) -> CollectionAnalyticsSummary:
    # fetch aggregated analytics summary for a given collection (chart over chart_days, tables over days)
    summary = CollectionAnalyticsSummary(collection_id=int(collection_id), days=int(chart_days))
    if not is_enabled() or not collection_id:
        try:
            from apps.marketplace.models import CollectionFavorite
            summary.total_favorites = CollectionFavorite.objects.filter(collection_id=collection_id).count()
        except Exception:
            pass
        return summary

    from apps.analytics.client import get_analytics_client

    try:
        client = get_analytics_client(force_enabled=True)
    except Exception as exc:
        report_analytics_error(exc, "get_collection_analytics client unavailable")
        try:
            from apps.marketplace.models import CollectionFavorite
            summary.total_favorites = CollectionFavorite.objects.filter(collection_id=collection_id).count()
        except Exception:
            pass
        return summary

    totals_params = {"collection_id": int(collection_id), "days": int(days)}
    chart_params = {"collection_id": int(collection_id), "days": int(chart_days)}

    # 1. Total counts & unique viewers (30 days)
    try:
        totals_query = """
            SELECT
                countIf(event_type = 'view') AS views,
                countIf(event_type = 'favorite') AS favorites,
                countIf(event_type = 'add_item') AS item_adds,
                uniqIf(if(user_id IS NOT NULL, toString(user_id), ip), event_type = 'view') AS unique_viewers
            FROM analytics_collection_events
            WHERE collection_id = %(collection_id)s
              AND event_time >= now() - toIntervalDay(%(days)s)
        """
        totals_rows = client.query_rows(totals_query, totals_params)
        if totals_rows:
            row = totals_rows[0]
            summary.total_views = int(row[0] or 0)
            summary.total_favorites = int(row[1] or 0)
            summary.total_item_adds = int(row[2] or 0)
            summary.unique_viewers = int(row[3] or 0)
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to query totals for collection_id={collection_id}",
        )

    # 2. Daily timeseries (views and favorites over chart_days = 14 days)
    try:
        ts_query = """
            SELECT
                toDate(event_time) AS dt,
                countIf(event_type = 'view') AS views_cnt,
                countIf(event_type = 'favorite') AS fav_cnt
            FROM analytics_collection_events
            WHERE collection_id = %(collection_id)s
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY dt
            ORDER BY dt ASC
        """
        for r in client.query_rows(ts_query, chart_params):
            d_str = str(r[0])
            summary.views_history.append(TimeseriesPoint(date=d_str, count=int(r[1] or 0)))
            summary.favorites_history.append(TimeseriesPoint(date=d_str, count=int(r[2] or 0)))
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to query timeseries for collection_id={collection_id}",
        )

    # 3. Countries breakdown (30 days)
    try:
        country_query = """
            SELECT
                if(country = '' OR country IS NULL, 'Unknown', country) AS c,
                count() AS cnt
            FROM analytics_collection_events
            WHERE collection_id = %(collection_id)s
              AND event_type = 'view'
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY c
            ORDER BY cnt DESC
            LIMIT 10
        """
        country_rows = client.query_rows(country_query, totals_params)
        total_c = sum(int(r[1]) for r in country_rows) or 1
        summary.countries_breakdown = [
            BreakdownItem(
                name=str(r[0]),
                count=int(r[1]),
                percentage=round((int(r[1]) / total_c) * 100, 1),
            )
            for r in country_rows
        ]
    except Exception as exc:
        report_analytics_error(
            exc,
            f"failed to query countries for collection_id={collection_id}",
        )

    return summary


def get_popular_apps(
    days: int = 7,
    limit: int = 10,
    event_type: str = "view",
) -> list[dict[str, Any]]:
    # get top application ids by event count over time
    if not is_enabled():
        return []

    from apps.analytics.client import get_analytics_client

    try:
        client = get_analytics_client(force_enabled=True)
        query = """
            SELECT app_id, count() AS cnt
            FROM analytics_app_events
            WHERE event_type = %(event_type)s
              AND event_time >= now() - toIntervalDay(%(days)s)
            GROUP BY app_id
            ORDER BY cnt DESC
            LIMIT %(limit)s
        """
        rows = client.query_rows(
            query,
            {"event_type": str(event_type), "days": int(days), "limit": int(limit)},
        )
        return [{"app_id": int(r[0]), "count": int(r[1])} for r in rows]
    except Exception as exc:
        report_analytics_error(exc, "get_popular_apps failed")
        return []


def get_popular_collections(
    days: int = 7,
    limit: int = 10,
    event_type: str = "view",
) -> list[dict[str, Any]]:
    # get top collection ids by event count over time
    if not is_enabled():
        return []

    from apps.analytics.client import get_analytics_client

    try:
        client = get_analytics_client(force_enabled=True)
        query = """
            SELECT collection_id, count() AS cnt
            FROM analytics_collection_events
            WHERE event_type = %(event_type)s
              AND event_time >= now() - toIntervalDay(%(days)s)
              AND is_public = 1
            GROUP BY collection_id
            ORDER BY cnt DESC
            LIMIT %(limit)s
        """
        rows = client.query_rows(
            query,
            {"event_type": str(event_type), "days": int(days), "limit": int(limit)},
        )
        return [{"collection_id": int(r[0]), "count": int(r[1])} for r in rows]
    except Exception as exc:
        report_analytics_error(exc, "get_popular_collections failed")
        return []
