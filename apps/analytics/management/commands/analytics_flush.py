# management command: manually flush redis analytics buffer to clickhouse

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.buffer import get_all_buffer_lengths
from apps.analytics.config import get_flush_batch_size
from apps.analytics.flusher import flush_all_analytics_buffers
from apps.analytics.services import is_enabled


class Command(BaseCommand):
    help = "Flush buffered analytics events from Redis into ClickHouse."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum rows to flush per table in a single batch (default: from Constance/settings).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Flush even when ANALYTICS_ENABLED is False.",
        )

    def handle(self, *args: object, **options: object) -> None:
        force = bool(options.get("force"))
        batch_size_opt = options.get("batch_size")
        batch_size = int(batch_size_opt) if batch_size_opt is not None else get_flush_batch_size()

        if not is_enabled() and not force:
            raise CommandError(
                "Analytics is disabled. Set ANALYTICS_ENABLED=True or pass --force."
            )

        initial_counts = get_all_buffer_lengths()
        self.stdout.write(f"Current analytics buffer sizes: {initial_counts}")

        total_pending = sum(initial_counts.values())
        if total_pending == 0:
            self.stdout.write(self.style.SUCCESS("All analytics buffers are currently empty."))
            return

        self.stdout.write(f"Flushing up to {batch_size} rows per table...")
        flushed_stats = flush_all_analytics_buffers(batch_size=batch_size)

        total_flushed = sum(flushed_stats.values())
        for table, count in flushed_stats.items():
            if count > 0:
                self.stdout.write(self.style.SUCCESS(f"  - {table}: {count} rows flushed"))
            else:
                self.stdout.write(f"  - {table}: 0 rows flushed")

        remaining_counts = get_all_buffer_lengths()
        self.stdout.write(
            self.style.SUCCESS(
                f"Flush completed: {total_flushed} rows inserted. Remaining in buffers: {remaining_counts}"
            )
        )
