# analytics unit tests — models, extractors, client, tasks, services

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator
from unittest.mock import MagicMock, patch

from django.http import HttpRequest
from django.test import SimpleTestCase, override_settings

from apps.analytics.buffer import (
    clear_buffer,
    clear_memory_buffers,
    get_all_buffer_lengths,
    get_buffer_length,
    pop_buffer_batch,
    push_event_to_buffer,
    set_memory_fallback,
)
from apps.analytics.client import (
    ClickHouseAnalyticsClient,
    NullAnalyticsClient,
    get_analytics_client,
    reset_analytics_client,
)
from apps.analytics.extractors import extract_request_meta
from apps.analytics.flusher import (
    flush_all_analytics_buffers,
    flush_table_buffer,
    is_circuit_open,
    record_circuit_failure,
    record_circuit_success,
)
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
    get_app_of_the_day_id,
    get_collection_analytics,
    get_popular_apps,
    get_popular_collections,
    get_similar_app_ids,
    is_enabled,
    ping,
    track_app_collection_add,
    track_app_collection_remove,
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
    def test_extract_with_request(self) -> None:
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"
        request.META["HTTP_CF_IPCOUNTRY"] = "KZ"
        request.META["HTTP_REFERER"] = "http://lunastore.app/catalog"

        meta = extract_request_meta(request)
        self.assertEqual(meta.ip, "192.168.1.100")
        self.assertEqual(meta.country, "KZ")
        self.assertEqual(meta.referer, "http://lunastore.app/catalog")
        self.assertTrue("Windows" in meta.os_name or meta.os_name != "")

    def test_extract_authenticated_user(self) -> None:
        request = HttpRequest()
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.pk = 999
        request.user = mock_user

        meta = extract_request_meta(request)
        self.assertEqual(meta.user_id, 999)


class AnalyticsDisabledTests(SimpleTestCase):
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()

    def tearDown(self) -> None:
        reset_analytics_client()
        clear_memory_buffers()

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
            track_app_view(None, 42)
            self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 0)

    def test_track_collection_view_skipped_when_disabled(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            track_collection_view(None, 99)
            self.assertEqual(get_buffer_length(CollectionEvent.TABLE_NAME), 0)

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
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()
        record_circuit_success()

    def tearDown(self) -> None:
        reset_analytics_client()
        clear_memory_buffers()

    def test_track_app_view_buffers(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            track_app_view(None, 42, category_id=3)
            self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)
            rows = pop_buffer_batch(AppEvent.TABLE_NAME)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row[1], "view")
            self.assertEqual(row[2], 42)
            self.assertEqual(row[4], 3)

    def test_track_app_download_buffers(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            track_app_download(None, 10, distribution_id=55)
            self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)
            rows = pop_buffer_batch(AppEvent.TABLE_NAME)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row[1], "download")
            self.assertEqual(row[2], 10)
            self.assertEqual(row[3], 55)

    def test_track_app_like_and_rate(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            track_app_like(None, 12, is_like=True)
            track_app_rate(None, 12, rating=5)
            track_app_collection_add(None, 12, collection_id=77)
            track_app_collection_remove(None, 12, collection_id=77)
            self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 4)

    def test_track_collection_events_buffers(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            track_collection_view(None, 7, owner_id=2)
            track_collection_favorite(None, 7, is_favorite=True)
            track_collection_item_change(None, 7, app_id=10, is_added=True)
            self.assertEqual(get_buffer_length(CollectionEvent.TABLE_NAME), 3)

    def test_track_app_download_deduplication(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        req = HttpRequest()
        req.META["REMOTE_ADDR"] = "192.0.2.100"
        with patch("constance.config", mock_config):
            with patch("django.core.cache.cache.add", side_effect=[True, False]):
                track_app_download(req, 100, distribution_id=1, deduplicate=True)
                self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)

                track_app_download(req, 100, distribution_id=1, deduplicate=True)
                self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)

    def test_track_app_view_deduplication(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        req = HttpRequest()
        req.META["REMOTE_ADDR"] = "192.0.2.101"
        with patch("constance.config", mock_config):
            with patch("django.core.cache.cache.add", side_effect=[True, False]):
                track_app_view(req, 200, deduplicate=True)
                self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)

                track_app_view(req, 200, deduplicate=True)
                self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)


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

    def test_get_popular_apps_with_category(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.return_value = [(55, 10)]

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                popular = get_popular_apps(days=7, limit=5, category_id=3)
                self.assertEqual(popular[0]["app_id"], 55)
                call_kwargs = mock_client.query_rows.call_args
                self.assertIn("category_id", call_kwargs[0][1])
                self.assertEqual(call_kwargs[0][1]["category_id"], 3)

    def test_get_app_of_the_day_id(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.return_value = [(42, 99)]
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                with patch("django.core.cache.cache", mock_cache):
                    app_id = get_app_of_the_day_id()
        self.assertEqual(app_id, 42)
        mock_cache.set.assert_called_once()

    def test_get_similar_app_ids(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.side_effect = [
            [(1,), (2,)],
            [(10, 5), (11, 3)],
        ]
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                with patch("django.core.cache.cache", mock_cache):
                    ids = get_similar_app_ids(7, limit=6)
        self.assertEqual(ids, [10, 11])

    def test_get_similar_app_ids_insufficient_history(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.query_rows.return_value = [(1,)]
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                with patch("django.core.cache.cache", mock_cache):
                    ids = get_similar_app_ids(7, min_history=2)
        self.assertEqual(ids, [])


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


class AnalyticsBufferTests(SimpleTestCase):
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()

    def tearDown(self) -> None:
        clear_memory_buffers()

    def test_push_and_pop_buffer(self) -> None:
        row1 = ["2026-09-25T12:00:00+00:00", "view", 1, None, None, None, "", "", "", "", "", "", "", "{}"]
        row2 = ["2026-09-25T12:01:00+00:00", "download", 2, None, None, None, "", "", "", "", "", "", "", "{}"]

        success1 = push_event_to_buffer("test_table", row1)
        success2 = push_event_to_buffer("test_table", row2)

        self.assertTrue(success1)
        self.assertTrue(success2)
        self.assertEqual(get_buffer_length("test_table"), 2)

        popped = pop_buffer_batch("test_table", batch_size=1)
        self.assertEqual(len(popped), 1)
        self.assertEqual(popped[0][1], "view")
        self.assertEqual(get_buffer_length("test_table"), 1)

        popped_remaining = pop_buffer_batch("test_table", batch_size=10)
        self.assertEqual(len(popped_remaining), 1)
        self.assertEqual(popped_remaining[0][1], "download")
        self.assertEqual(get_buffer_length("test_table"), 0)

    def test_pop_empty_buffer(self) -> None:
        self.assertEqual(pop_buffer_batch("empty_table"), [])

    def test_buffer_lengths_dict(self) -> None:
        push_event_to_buffer(AppEvent.TABLE_NAME, ["dummy"])
        push_event_to_buffer(CollectionEvent.TABLE_NAME, ["dummy"])
        lengths = get_all_buffer_lengths()
        self.assertEqual(lengths[AppEvent.TABLE_NAME], 1)
        self.assertEqual(lengths[CollectionEvent.TABLE_NAME], 1)
        self.assertEqual(lengths["analytics_events"], 0)

    def test_clear_buffer(self) -> None:
        push_event_to_buffer("test_table", ["sample"])
        self.assertEqual(get_buffer_length("test_table"), 1)
        clear_buffer("test_table")
        self.assertEqual(get_buffer_length("test_table"), 0)


class AnalyticsFlusherTests(SimpleTestCase):
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()
        record_circuit_success()

    def tearDown(self) -> None:
        clear_memory_buffers()
        record_circuit_success()

    def test_flush_table_buffer_success(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()

        row1 = ["2026-09-25T12:00:00+00:00", "view", 10, None, None, None, "", "", "", "", "", "", "", "{}"]
        row2 = ["2026-09-25T12:05:00+00:00", "download", 10, None, None, None, "", "", "", "", "", "", "", "{}"]
        push_event_to_buffer(AppEvent.TABLE_NAME, row1)
        push_event_to_buffer(AppEvent.TABLE_NAME, row2)

        with patch("constance.config", mock_config):
            flushed = flush_table_buffer(AppEvent.TABLE_NAME, batch_size=1000, client=mock_client)

        self.assertEqual(flushed, 2)
        mock_client.insert_rows.assert_called_once()
        args, kwargs = mock_client.insert_rows.call_args
        self.assertEqual(args[0], AppEvent.TABLE_NAME)
        self.assertEqual(len(args[1]), 2)
        self.assertEqual(args[2], AppEvent.COLUMN_NAMES)
        self.assertEqual(kwargs.get("wait_for_async_insert"), 0)
        self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 0)

    def test_flush_table_buffer_requeues_on_error(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.insert_rows.side_effect = RuntimeError("ClickHouse connection refused")

        row = ["2026-09-25T12:00:00+00:00", "view", 99, None, None, None, "", "", "", "", "", "", "", "{}"]
        push_event_to_buffer(AppEvent.TABLE_NAME, row)

        with _quiet_analytics_logs():
            with patch("constance.config", mock_config):
                flushed = flush_table_buffer(AppEvent.TABLE_NAME, batch_size=1000, client=mock_client)

        self.assertEqual(flushed, 0)
        self.assertTrue(is_circuit_open())
        # row should be requeued back into buffer
        self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)

    def test_flush_skipped_when_circuit_breaker_open(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        record_circuit_failure()

        push_event_to_buffer(AppEvent.TABLE_NAME, ["sample"])
        with patch("constance.config", mock_config):
            flushed = flush_table_buffer(AppEvent.TABLE_NAME, client=mock_client)

        self.assertEqual(flushed, 0)
        mock_client.insert_rows.assert_not_called()
        self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 1)

    def test_flush_all_analytics_buffers(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()

        push_event_to_buffer(
            AppEvent.TABLE_NAME,
            ["2026-09-25T12:00:00+00:00", "view", 1, None, None, None, "", "", "", "", "", "", "", "{}"],
        )
        push_event_to_buffer(
            CollectionEvent.TABLE_NAME,
            ["2026-09-25T12:00:00+00:00", "view", 2, None, None, None, 0, 1, "", "", "", "", "", "", "{}"],
        )

        with patch("constance.config", mock_config):
            stats = flush_all_analytics_buffers(client=mock_client)

        self.assertEqual(stats[AppEvent.TABLE_NAME], 1)
        self.assertEqual(stats[CollectionEvent.TABLE_NAME], 1)
        self.assertEqual(stats["analytics_events"], 0)


class AnalyticsCommandAndTaskTests(SimpleTestCase):
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()
        record_circuit_success()

    def tearDown(self) -> None:
        clear_memory_buffers()
        record_circuit_success()

    def test_flush_analytics_task(self) -> None:
        from apps.analytics.tasks import flush_analytics_task

        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()

        push_event_to_buffer(
            AppEvent.TABLE_NAME,
            ["2026-09-25T12:00:00+00:00", "view", 5, None, None, None, "", "", "", "", "", "", "", "{}"],
        )

        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                result = flush_analytics_task.call()

        self.assertEqual(result.get(AppEvent.TABLE_NAME), 1)
        mock_client.insert_rows.assert_called_once()

    def test_analytics_flush_management_command(self) -> None:
        from io import StringIO
        from django.core.management import call_command

        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()

        push_event_to_buffer(
            AppEvent.TABLE_NAME,
            ["2026-09-25T12:00:00+00:00", "view", 77, None, None, None, "", "", "", "", "", "", "", "{}"],
        )

        out = StringIO()
        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client", return_value=mock_client):
                call_command("analytics_flush", stdout=out)

        output = out.getvalue()
        self.assertIn("Flushing up to 1000 rows", output)
        self.assertIn("analytics_app_events: 1 rows flushed", output)


class AnalyticsConfigTests(SimpleTestCase):
    def test_default_config_values(self) -> None:
        from apps.analytics.config import (
            DEFAULT_BUFFER_MAX_SIZE,
            DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
            DEFAULT_FLUSH_BATCH_SIZE,
            DEFAULT_FLUSH_INTERVAL,
            DEFAULT_FLUSH_THRESHOLD,
            get_buffer_max_size,
            get_circuit_breaker_timeout,
            get_flush_batch_size,
            get_flush_interval,
            get_flush_threshold,
        )

        mock_config = MagicMock()
        mock_config.ANALYTICS_CIRCUIT_BREAKER_TIMEOUT = None
        mock_config.ANALYTICS_FLUSH_THRESHOLD = None
        mock_config.ANALYTICS_BUFFER_MAX_SIZE = None
        mock_config.ANALYTICS_FLUSH_BATCH_SIZE = None
        mock_config.ANALYTICS_FLUSH_INTERVAL = None

        with patch("constance.config", mock_config):
            self.assertEqual(get_circuit_breaker_timeout(), DEFAULT_CIRCUIT_BREAKER_TIMEOUT)
            self.assertEqual(get_flush_threshold(), DEFAULT_FLUSH_THRESHOLD)
            self.assertEqual(get_buffer_max_size(), DEFAULT_BUFFER_MAX_SIZE)
            self.assertEqual(get_flush_batch_size(), DEFAULT_FLUSH_BATCH_SIZE)
            self.assertEqual(get_flush_interval(), DEFAULT_FLUSH_INTERVAL)

    def test_settings_override(self) -> None:
        from apps.analytics.config import (
            get_buffer_max_size,
            get_circuit_breaker_timeout,
            get_flush_batch_size,
            get_flush_interval,
            get_flush_threshold,
        )

        mock_config = MagicMock()
        mock_config.ANALYTICS_CIRCUIT_BREAKER_TIMEOUT = None
        mock_config.ANALYTICS_FLUSH_THRESHOLD = None
        mock_config.ANALYTICS_BUFFER_MAX_SIZE = None
        mock_config.ANALYTICS_FLUSH_BATCH_SIZE = None
        mock_config.ANALYTICS_FLUSH_INTERVAL = None

        with patch("constance.config", mock_config):
            with override_settings(
                ANALYTICS_CIRCUIT_BREAKER_TIMEOUT=45,
                ANALYTICS_FLUSH_THRESHOLD=300,
                ANALYTICS_BUFFER_MAX_SIZE=50000,
                ANALYTICS_FLUSH_BATCH_SIZE=250,
                ANALYTICS_FLUSH_INTERVAL=2.5,
            ):
                self.assertEqual(get_circuit_breaker_timeout(), 45)
                self.assertEqual(get_flush_threshold(), 300)
                self.assertEqual(get_buffer_max_size(), 50000)
                self.assertEqual(get_flush_batch_size(), 250)
                self.assertEqual(get_flush_interval(), 2.5)

    def test_constance_override_takes_priority(self) -> None:
        from apps.analytics.config import (
            get_buffer_max_size,
            get_circuit_breaker_timeout,
            get_flush_batch_size,
            get_flush_interval,
            get_flush_threshold,
        )

        mock_config = MagicMock()
        mock_config.ANALYTICS_CIRCUIT_BREAKER_TIMEOUT = 90
        mock_config.ANALYTICS_FLUSH_THRESHOLD = 700
        mock_config.ANALYTICS_BUFFER_MAX_SIZE = 200000
        mock_config.ANALYTICS_FLUSH_BATCH_SIZE = 500
        mock_config.ANALYTICS_FLUSH_INTERVAL = 10.0

        with patch("constance.config", mock_config):
            with override_settings(
                ANALYTICS_CIRCUIT_BREAKER_TIMEOUT=15,
                ANALYTICS_FLUSH_THRESHOLD=100,
            ):
                self.assertEqual(get_circuit_breaker_timeout(), 90)
                self.assertEqual(get_flush_threshold(), 700)
                self.assertEqual(get_buffer_max_size(), 200000)
                self.assertEqual(get_flush_batch_size(), 500)
                self.assertEqual(get_flush_interval(), 10.0)

    def test_record_circuit_failure_with_custom_timeout(self) -> None:
        from django.core.cache import cache

        mock_config = MagicMock()
        mock_config.ANALYTICS_CIRCUIT_BREAKER_TIMEOUT = 120

        with patch("constance.config", mock_config):
            with patch.object(cache, "set") as mock_cache_set:
                record_circuit_failure()
                mock_cache_set.assert_called_with("analytics:circuit_open", 1, timeout=120)

                record_circuit_failure(timeout=15)
                mock_cache_set.assert_called_with("analytics:circuit_open", 1, timeout=15)


class AnalyticsSecurityTests(SimpleTestCase):
    def setUp(self) -> None:
        set_memory_fallback(True)
        clear_memory_buffers()

    def tearDown(self) -> None:
        clear_memory_buffers()

    def test_invalid_table_name_rejected(self) -> None:
        # invalid table names
        malicious_tables = [
            "analytics_app_events; FLUSHALL",
            "../../etc/passwd",
            "analytics:buffer:hack",
            "table with spaces",
            "table\nnewline",
            "a" * 100,  # exceeds 64 chars
        ]
        for tbl in malicious_tables:
            res = push_event_to_buffer(tbl, ["test"])
            self.assertFalse(res)
            self.assertEqual(get_buffer_length(tbl), 0)
            self.assertEqual(pop_buffer_batch(tbl), [])

    def test_oversized_payload_rejected(self) -> None:
        # oversized payload
        huge_payload = ["A" * 70_000]
        res = push_event_to_buffer(AppEvent.TABLE_NAME, huge_payload)
        self.assertFalse(res)
        self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 0)

    def test_non_retryable_error_does_not_poison_queue(self) -> None:
        # non-retryable error handling
        class DataError(Exception):
            pass

        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_client = MagicMock()
        mock_client.insert_rows.side_effect = DataError("Type mismatch: cannot parse column")

        push_event_to_buffer(
            AppEvent.TABLE_NAME,
            ["2026-09-25T12:00:00+00:00", "view", 1, None, None, None, "", "", "", "", "", "", "", "{}"],
        )

        with patch("constance.config", mock_config):
            with _quiet_analytics_logs():
                flushed = flush_table_buffer(AppEvent.TABLE_NAME, client=mock_client)

        self.assertEqual(flushed, 0)
        # Poison pill should NOT be requeued back into the buffer
        self.assertEqual(get_buffer_length(AppEvent.TABLE_NAME), 0)

    def test_config_bounds_clamping(self) -> None:
        from apps.analytics.config import (
            get_buffer_max_size,
            get_circuit_breaker_timeout,
            get_flush_batch_size,
            get_flush_interval,
            get_flush_threshold,
        )

        mock_config = MagicMock()
        mock_config.ANALYTICS_CIRCUIT_BREAKER_TIMEOUT = -10
        mock_config.ANALYTICS_FLUSH_THRESHOLD = 0
        mock_config.ANALYTICS_BUFFER_MAX_SIZE = 10
        mock_config.ANALYTICS_FLUSH_BATCH_SIZE = 999_999
        mock_config.ANALYTICS_FLUSH_INTERVAL = 0.001

        with patch("constance.config", mock_config):
            self.assertEqual(get_circuit_breaker_timeout(), 1)
            self.assertEqual(get_flush_threshold(), 1)
            self.assertEqual(get_buffer_max_size(), 100)
            self.assertEqual(get_flush_batch_size(), 50_000)
            self.assertEqual(get_flush_interval(), 0.1)
