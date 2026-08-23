# management command: apply clickhouse/tables/*.sql

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.client import get_analytics_client
from apps.analytics.reporting import AnalyticsUnavailableError
from apps.analytics.services import is_enabled

logger = logging.getLogger("analytics")


class Command(BaseCommand):
    help = "Apply SQL files from clickhouse/tables/ to ClickHouse."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even when ANALYTICS_ENABLED is False.",
        )

    def handle(self, *args: object, **options: object) -> None:
        force = bool(options.get("force"))
        if not is_enabled() and not force:
            raise CommandError(
                "Analytics is disabled. Set ANALYTICS_ENABLED=True "
                "or pass --force."
            )

        schema_dir = Path(settings.BASE_DIR) / "clickhouse" / "tables"
        if not schema_dir.is_dir():
            raise CommandError(f"Schema directory not found: {schema_dir}")

        sql_files: List[Path] = sorted(schema_dir.glob("*.sql"))
        if not sql_files:
            raise CommandError(f"No .sql files in {schema_dir}")

        try:
            client = get_analytics_client(force_enabled=True)
        except AnalyticsUnavailableError as exc:
            raise CommandError(f"ClickHouse is unreachable: {exc}") from exc

        try:
            if not client.ping():
                raise CommandError("ClickHouse is unreachable.")

            for sql_path in sql_files:
                sql = sql_path.read_text(encoding="utf-8").strip()
                if not sql:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping empty file: {sql_path.name}"
                        )
                    )
                    continue
                self.stdout.write(f"Applying {sql_path.name}...")
                try:
                    # one file = one statement (no naive ; splitting)
                    statement = sql.rstrip().rstrip(";").strip()
                    if statement:
                        client.execute(statement)
                except Exception as exc:
                    logger.exception("failed applying %s", sql_path.name)
                    raise CommandError(
                        f"Failed applying {sql_path.name}: {exc}"
                    ) from exc
                self.stdout.write(
                    self.style.SUCCESS(f"Applied {sql_path.name}")
                )
        finally:
            client.close()

        self.stdout.write(
            self.style.SUCCESS("Analytics schema migrate complete.")
        )
