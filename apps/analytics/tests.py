# analytics unit tests — no live clickhouse/db needed

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.analytics.client import (
    NullAnalyticsClient,
    get_analytics_client,
    reset_analytics_client,
)
from apps.analytics.reporting import (
    AnalyticsUnavailableError,
    optional_user_id,
    report_analytics_error,
)
from apps.analytics.services import is_enabled, ping, track_event


@contextmanager
def _quiet_analytics_logs() -> Iterator[None]:
    # expected-error tests should not spam the test runner
    with patch("apps.analytics.client.logger.exception"):
        with patch("apps.analytics.reporting.logger.error"):
            with patch("apps.analytics.reporting.logger.warning"):
                yield


class AnalyticsDisabledTests(SimpleTestCase):
    # flag off → quiet no-op

    def tearDown(self) -> None:
        reset_analytics_client()

    def test_is_enabled_false(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            self.assertFalse(is_enabled())

    def test_ping_returns_false_without_network(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            with patch("apps.analytics.client.get_analytics_client") as mock_get:
                self.assertFalse(ping())
                mock_get.assert_not_called()

    def test_track_event_does_not_enqueue(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            with patch(
                "apps.analytics.tasks.insert_analytics_event"
            ) as mock_task:
                track_event("page_view", user_id=1, properties={"path": "/"})
                mock_task.enqueue.assert_not_called()

    @override_settings(ANALYTICS_ENABLED=False)
    def test_get_client_returns_null(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = False
        with patch("constance.config", mock_config):
            client = get_analytics_client()
            self.assertIsInstance(client, NullAnalyticsClient)
            self.assertFalse(client.ping())


class AnalyticsEnabledGateTests(SimpleTestCase):
    # flag on → enqueue without needing a real ch

    def tearDown(self) -> None:
        reset_analytics_client()

    def test_is_enabled_true(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            self.assertTrue(is_enabled())

    def test_track_event_enqueues_task(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch(
                "apps.analytics.tasks.insert_analytics_event"
            ) as mock_task:
                mock_task.enqueue = MagicMock()
                track_event(
                    "page_view",
                    user_id=42,
                    properties={"path": "/apps"},
                )
                mock_task.enqueue.assert_called_once()
                args, _kwargs = mock_task.enqueue.call_args
                self.assertEqual(args[0], "page_view")
                self.assertEqual(args[1], 42)

    def test_track_event_keeps_none_user_id(self) -> None:
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        with patch("constance.config", mock_config):
            with patch(
                "apps.analytics.tasks.insert_analytics_event"
            ) as mock_task:
                mock_task.enqueue = MagicMock()
                track_event("anon_view")
                args, _kwargs = mock_task.enqueue.call_args
                self.assertIsNone(args[1])

    def test_get_client_raises_when_connect_fails(self) -> None:
        reset_analytics_client()
        mock_config = MagicMock()
        mock_config.ANALYTICS_ENABLED = True
        mock_ch = MagicMock()
        mock_ch.get_client.side_effect = OSError("nope")
        with patch("constance.config", mock_config):
            with patch.dict("sys.modules", {"clickhouse_connect": mock_ch}):
                with _quiet_analytics_logs():
                    with self.assertRaises(AnalyticsUnavailableError):
                        get_analytics_client(force_enabled=True)
        reset_analytics_client()


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
