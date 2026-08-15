# analytics unit tests — models, extractors, client, tasks, services

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator
from unittest.mock import MagicMock, patch

from django.http import HttpRequest
from django.test import SimpleTestCase, override_settings

from apps.analytics.client import (
    ClickHouseAnalyticsClient,
    NullAnalyticsClient,
    get_analytics_client,
    reset_analytics_client,
)
from apps.analytics.extractors import extract_request_meta
from apps.analytics.models import (
    AppAnalyticsSummary,
    AppEvent,
    AppEventType,
    BaseAnalyticsEvent,
    BreakdownItem,
    CollectionAnalyticsSummary,
    CollectionEvent,
    CollectionEventType,
    TimeseriesPoint,
)
from apps.analytics.reporting import (
    AnalyticsUnavailableError,
    optional_user_id,
    report_analytics_error,
)
from apps.analytics.services import (
    get_app_analytics,
    get_collection_analytics,
    get_popular_apps,
    get_popular_collections,
    is_enabled,
    ping,
    track_app_collection_add,
    track_app_download,
    track_app_event,
    track_app_like,
    track_app_rate,
    track_app_view,
    track_collection_event,
    track_collection_favorite,
    track_collection_item_change,
    track_collection_view,
    track_event,
)


@contextmanager
def _quiet_analytics_logs() -> Iterator[None]:
    # expected-error tests should not spam the test runner
    with patch("apps.analytics.client.logger.exception"):
        with patch("apps.analytics.reporting.logger.error"):
            with patch("apps.analytics.reporting.logger.warning"):
                with patch("apps.analytics.services.logger.error"):
                    with patch("apps.analytics.tasks.logger.error"):
                        yield


class AnalyticsModelsTests(SimpleTestCase):
    def test_base_event_to_dict(self) -> None:
        now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = BaseAnalyticsEvent(
            event_time=now,
            user_id=1,
            ip="127.0.0.1",
            country="US",
            os_name="Windows XP",
            browser="IE 6.0",
            meta={"key": "val"},
        )
        d = event.to_dict()
        self.assertEqual(d["user_id"], 1)
        self.assertEqual(d["country"], "US")
        self.assertEqual(d["event_time"], now.isoformat())
        self.assertEqual(event.meta_json(), '{"key": "val"}')

    def test_app_event_to_clickhouse_row(self) -> None:
        now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = AppEvent(
            event_time=now,
            event_type=AppEventType.DOWNLOAD,
            app_id=42,
            distribution_id=101,
            category_id=5,
            user_id=7,
            ip="192.168.1.5",
            country="RU",
            os_name="Windows 2000",
            os_version="5.0",
            browser="RetroIE 6",
            referer="https://example.com",
            session_id="sess_123",
            meta={"source": "direct"},
        )
        row = event.to_clickhouse_row()
        self.assertEqual(len(row), len(AppEvent.COLUMN_NAMES))
        self.assertEqual(row[0], now)
        self.assertEqual(row[1], "download")
        self.assertEqual(row[2], 42)
        self.assertEqual(row[3], 101)
        self.assertEqual(row[4], 5)
        self.assertEqual(row[5], 7)
        self.assertEqual(row[6], "192.168.1.5")
        self.assertEqual(row[7], "RU")
        self.assertEqual(row[8], "Windows 2000")
        self.assertEqual(row[9], "5.0")
        self.assertEqual(row[10], "RetroIE 6")
        self.assertEqual(row[11], "https://example.com")
        self.assertEqual(row[12], "sess_123")
        self.assertEqual(row[13], '{"source": "direct"}')

    def test_collection_event_to_clickhouse_row(self) -> None:
        now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = CollectionEvent(
            event_time=now,
            event_type=CollectionEventType.FAVORITE,
            collection_id=88,
            owner_id=10,
            user_id=15,
            app_id=None,
            is_system=True,
            is_public=False,
            ip="10.0.0.1",
            country="BY",
            os_name="Linux",
            browser="Firefox 52",
        )
        row = event.to_clickhouse_row()
        self.assertEqual(len(row), len(CollectionEvent.COLUMN_NAMES))
        self.assertEqual(row[0], now)
        self.assertEqual(row[1], "favorite")
        self.assertEqual(row[2], 88)
        self.assertEqual(row[3], 10)
        self.assertEqual(row[4], 15)
        self.assertIsNone(row[5])
        self.assertEqual(row[6], 1)  # is_system
        self.assertEqual(row[7], 0)  # is_public
        self.assertEqual(row[8], "10.0.0.1")
        self.assertEqual(row[9], "BY")


class RequestMetadataExtractorTests(SimpleTestCase):
    def test_extract_none_request(self) -> None:
        meta = extract_request_meta(None)
        self.assertIsNone(meta["user_id"])
        self.assertEqual(meta["ip"], "")
        self.assertEqual(meta["country"], "")

    def test_extract_with_request(self) -> None:
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"
        request.META["HTTP_CF_IPCOUNTRY"] = "KZ"
        request.META["HTTP_REFERER"] = "http://lunastore.app/catalog"

        meta = extract_request_meta(request)
        self.assertEqual(meta["ip"], "192.168.1.100")
        self.assertEqual(meta["country"], "KZ")
        self.assertEqual(meta["referer"], "http://lunastore.app/catalog")
        self.assertTrue("Windows" in meta["os_name"] or meta["os_name"] != "")

    def test_extract_authenticated_user(self) -> None:
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.pk = 999
        request.user = mock_user

        meta = extract_request_meta(request)
        self.assertEqual(meta["user_id"], 999)


class AnalyticsDisabledTests(SimpleTestCase):
    def tearDown(self) -> None:
        reset_analytics_client()

    def test_is_enabled_false(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            self.assertFalse(is_enabled())

    def test_ping_returns_false_when_disabled(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            self.assertFalse(ping())

    def test_track_app_view_skipped_when_disabled(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                track_app_view(None, 42)
                mock_task.enqueue.assert_not_called()

    def test_track_collection_view_skipped_when_disabled(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_collection_event_task") as mock_task:
                track_collection_view(None, 99)
                mock_task.enqueue.assert_not_called()

    @override_settings(ANALYTICS_ENABLED=False)
    def test_get_client_returns_null_client(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            client = get_analytics_client()
            self.assertIsInstance(client, NullAnalyticsClient)
            self.assertFalse(client.ping())
            self.assertEqual(client.query_rows("SELECT 1"), [])


class AnalyticsEnabledTrackingTests(SimpleTestCase):
    def tearDown(self) -> None:
        reset_analytics_client()

    def test_track_app_view_enqueues(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                track_app_view(None, 42, category_id=3)
                mock_task.enqueue.assert_called_once()
                row = mock_task.enqueue.call_args[0][0]
                self.assertEqual(row[1], "view")
                self.assertEqual(row[2], 42)
                self.assertEqual(row[4], 3)

    def test_track_app_download_enqueues(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                track_app_download(None, 10, distribution_id=55)
                mock_task.enqueue.assert_called_once()
                row = mock_task.enqueue.call_args[0][0]
                self.assertEqual(row[1], "download")
                self.assertEqual(row[2], 10)
                self.assertEqual(row[3], 55)

    def test_track_app_like_and_rate(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                track_app_like(None, 12, is_like=True)
                track_app_rate(None, 12, rating=5)
                track_app_collection_add(None, 12, collection_id=77)
                self.assertEqual(mock_task.enqueue.call_count, 3)

    def test_track_collection_events_enqueues(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_collection_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                track_collection_view(None, 7, owner_id=2)
                track_collection_favorite(None, 7, is_favorite=True)
                track_collection_item_change(None, 7, app_id=10, is_added=True)
                self.assertEqual(mock_task.enqueue.call_count, 3)

    def test_track_app_download_deduplication(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        req = HttpRequest()
        req.META["REMOTE_ADDR"] = "192.0.2.100"
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                with patch("django.core.cache.cache.add", side_effect=[True, False]):
                    # first download -> enqueued
                    track_app_download(req, 100, distribution_id=1, deduplicate=True)
                    self.assertEqual(mock_task.enqueue.call_count, 1)

                    # second quick download -> deduplicated, not enqueued
                    track_app_download(req, 100, distribution_id=1, deduplicate=True)
                    self.assertEqual(mock_task.enqueue.call_count, 1)

    def test_track_app_view_deduplication(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        req = HttpRequest()
        req.META["REMOTE_ADDR"] = "192.0.2.101"
        with patch("constance.config", mock_config):
            with patch("apps.analytics.tasks.insert_app_event_task") as mock_task:
                mock_task.enqueue = MagicMock()
                with patch("django.core.cache.cache.add", side_effect=[True, False]):
                    # first view -> enqueued
                    track_app_view(req, 200, deduplicate=True)
                    self.assertEqual(mock_task.enqueue.call_count, 1)

                    # second quick view -> deduplicated, not enqueued
                    track_app_view(req, 200, deduplicate=True)
                    self.assertEqual(mock_task.enqueue.call_count, 1)


class AnalyticsReportingTests(SimpleTestCase):
    def tearDown(self) -> None:
        reset_analytics_client()

    def test_get_app_analytics_parses_results(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.side_effect = [
            # 1. totals: [views, downloads, likes, rates, uniq_views, uniq_downloads]
            [(150, 45, 12, 8, 110, 40)],
            # 2. timeseries: [(date, views, downloads)]
            [("2026-08-01", 10, 3), ("2026-08-02", 20, 5)],
            # 3. countries: [(country, count)]
            [("RU", 80), ("US", 30)],
            # 4. os: [(os_name, count)]
            [("Windows XP", 70), ("Windows 7", 40)],
            # 5. distributions: [(dist_id, count)]
            [(101, 35), (102, 10)],
        ]

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                summary = get_app_analytics(42)
                self.assertEqual(summary.app_id, 42)
                self.assertEqual(summary.total_views, 150)
                self.assertEqual(summary.total_downloads, 45)
                self.assertEqual(summary.total_likes, 12)
                self.assertEqual(summary.total_rates, 8)
                self.assertEqual(summary.unique_viewers, 110)
                self.assertEqual(summary.unique_downloaders, 40)
                self.assertEqual(len(summary.views_history), 2)
                self.assertEqual(summary.views_history[0].date, "2026-08-01")
                self.assertEqual(summary.views_history[0].count, 10)
                self.assertEqual(len(summary.countries_breakdown), 2)
                self.assertEqual(summary.countries_breakdown[0].name, "RU")
                self.assertEqual(len(summary.os_breakdown), 2)
                self.assertEqual(len(summary.distributions_breakdown), 2)
                self.assertEqual(summary.distributions_breakdown[0].name, "101")
                self.assertEqual(summary.distributions_breakdown[0].count, 35)

    def test_get_collection_analytics_parses_results(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.side_effect = [
            # 1. totals: [views, favorites, item_adds, unique_viewers]
            [(60, 15, 5, 45)],
            # 2. timeseries: [(date, views, favorites)]
            [("2026-08-01", 5, 2)],
            # 3. countries
            [("KZ", 30), ("RU", 15)],
        ]

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                summary = get_collection_analytics(88)
                self.assertEqual(summary.collection_id, 88)
                self.assertEqual(summary.total_views, 60)
                self.assertEqual(summary.total_favorites, 15)
                self.assertEqual(summary.total_item_adds, 5)
                self.assertEqual(summary.unique_viewers, 45)
                self.assertEqual(len(summary.views_history), 1)
                self.assertEqual(len(summary.countries_breakdown), 2)

    def test_get_popular_apps(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.return_value = [(101, 500), (102, 350)]

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                popular = get_popular_apps(days=7, limit=2)
                self.assertEqual(len(popular), 2)
                self.assertEqual(popular[0]["app_id"], 101)
                self.assertEqual(popular[0]["count"], 500)

    def test_get_popular_collections(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.return_value = [(5, 120)]

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                popular = get_popular_collections(days=7, limit=1)
                self.assertEqual(len(popular), 1)
                self.assertEqual(popular[0]["collection_id"], 5)
                self.assertEqual(popular[0]["count"], 120)


class ReportingHelpersTests(SimpleTestCase):
    def test_optional_user_id_keeps_none(self) -> None:
        self.assertIsNone(optional_user_id(None))
        self.assertEqual(optional_user_id(0), 0)
        self.assertEqual(optional_user_id(7), 7)

    @override_settings(SENTRY_ENABLED=True, SENTRY_DSN="http://dsn/1")
    def test_report_analytics_error_uses_sentry(self) -> None:
        scope = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = scope
        mock_cm.__exit__.return_value = False
        with _quiet_analytics_logs():
            with patch("sentry_sdk.push_scope", return_value=mock_cm):
                with patch("sentry_sdk.capture_exception") as mock_capture:
                    report_analytics_error(RuntimeError("x"), "hello")
        mock_capture.assert_called_once()
        scope.set_tag.assert_called_once_with("module", "analytics")

    @override_settings(SENTRY_ENABLED=False, SENTRY_DSN="")
    def test_report_skips_sentry_when_disabled(self) -> None:
        with _quiet_analytics_logs():
            with patch("sentry_sdk.capture_exception") as mock_capture:
                report_analytics_error(RuntimeError("x"), "hello")
        mock_capture.assert_not_called()

    def test_summary_chart_bars_calculation(self) -> None:
        today = datetime.now(timezone.utc).date()
        d1 = (today - timedelta(days=1)).isoformat()
        d2 = today.isoformat()
        summary = AppAnalyticsSummary(
            app_id=1,
            days=2,
            views_history=[TimeseriesPoint(date=d1, count=100), TimeseriesPoint(date=d2, count=50)],
            downloads_history=[TimeseriesPoint(date=d1, count=20), TimeseriesPoint(date=d2, count=10)],
        )
        self.assertTrue(summary.has_chart_data)
        bars = summary.chart_bars
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].date, d1)
        self.assertEqual(bars[0].height1, 85)
        self.assertEqual(bars[0].height2, 17)
        self.assertEqual(bars[1].date, d2)
        self.assertEqual(bars[1].height1, 42)
        self.assertEqual(bars[1].height2, 8)

    def test_summary_empty_chart_bars(self) -> None:
        summary = AppAnalyticsSummary(app_id=1)
        self.assertFalse(summary.has_chart_data)
        self.assertEqual(summary.chart_bars, [])
