# management command: ping clickhouse

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services import is_enabled, ping


class Command(BaseCommand):
    help = "Ping ClickHouse when analytics is enabled."

    def handle(self, *args: object, **options: object) -> None:
        if not is_enabled():
            self.stdout.write(
                self.style.WARNING("Analytics is disabled (ANALYTICS_ENABLED=False).")
            )
            return

        ok = ping()
        if not ok:
            raise CommandError("ClickHouse ping failed.")

        self.stdout.write(self.style.SUCCESS("ClickHouse ping ok."))
