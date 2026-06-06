"""Management command to test GlitchTip (Sentry) integration."""
import logging
from typing import Any

import sentry_sdk
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger("core")


class Command(BaseCommand):
    """Send a test error event to GlitchTip (aka Sentry) to verify integration is working."""

    help = "Send a test error event to GlitchTip (Sentry) to verify integration."

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the test command."""
        # step 1: check if sentry is enabled and configured
        if not getattr(settings, "SENTRY_ENABLED", False):
            self.stderr.write(
                self.style.ERROR(
                    "SENTRY_ENABLED is False. Set SENTRY_ENABLED=\"True\" in .env"
                )
            )
            return

        dsn = getattr(settings, "SENTRY_DSN", "")
        if not dsn:
            self.stderr.write(
                self.style.ERROR(
                    "SENTRY_DSN is empty. Set SENTRY_DSN in .env"
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(f"DSN: {dsn[:40]}...")
        )
        self.stdout.write(
            self.style.WARNING(
                f"Environment: {getattr(settings, 'SENTRY_ENVIRONMENT', 'unknown')}"
            )
        )

        # step 2: check if sentry sdk client is active
        client = sentry_sdk.get_client()
        if not client.is_active():
            self.stderr.write(
                self.style.ERROR(
                    "Sentry SDK client is not active. "
                    "Check DSN and SENTRY_ENABLED in .env"
                )
            )
            return

        self.stdout.write(self.style.SUCCESS("Sentry SDK client is active."))

        # step 3: send a test exception event
        try:
            raise RuntimeError("GlitchTip test error from sentry_test command")
        except RuntimeError:
            event_id = sentry_sdk.capture_exception()

        if event_id:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Test exception sent! Event ID: {event_id}"
                )
            )
        else:
            self.stderr.write(
                self.style.ERROR(
                    "Failed to send test exception. "
                    "Check DSN, network, and GlitchTip availability."
                )
            )
            return

        # step 4: send a test message event
        message_id = sentry_sdk.capture_message(
            "GlitchTip test message from sentry_test command",
            level="info",
        )
        if message_id:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Test message sent! Event ID: {message_id}"
                )
            )

        # step 5: flush pending events
        sentry_sdk.flush(timeout=5)

        self.stdout.write(
            self.style.SUCCESS(
                "All test events sent and flushed. "
                "Check your GlitchTip dashboard for the events."
            )
        )
