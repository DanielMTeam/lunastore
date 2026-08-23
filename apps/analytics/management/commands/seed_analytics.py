# management command: seed 30 days of realistic analytics data
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from constance import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.client import get_analytics_client
from apps.analytics.reporting import AnalyticsUnavailableError
from apps.marketplace.models import Application, Collection, Distribution

logger = logging.getLogger("analytics")

SAMPLE_OS = [
    ("Windows", "5.1", "Windows XP", 0.50),
    ("Windows", "5.0", "Windows 2000", 0.20),
    ("Windows", "4.10", "Windows 98", 0.12),
    ("Windows", "6.1", "Windows 7", 0.10),
    ("Windows", "6.0", "Windows Vista", 0.05),
    ("Windows", "4.0", "Windows 95", 0.03),
]

SAMPLE_BROWSERS = [
    ("MSIE 6.0", 0.40),
    ("MSIE 5.5", 0.15),
    ("Firefox 2.0", 0.15),
    ("Opera 9.80", 0.12),
    ("MSIE 8.0", 0.10),
    ("RetroZilla", 0.08),
]

SAMPLE_COUNTRIES = [
    ("RU", 0.35),
    ("US", 0.20),
    ("DE", 0.12),
    ("UA", 0.10),
    ("BY", 0.08),
    ("KZ", 0.05),
    ("GB", 0.05),
    ("PL", 0.03),
    ("FR", 0.02),
]


def weighted_choice(choices):
    r = random.random()
    cumulative = 0.0
    for item in choices:
        cumulative += item[-1]
        if r <= cumulative:
            return item[:-1]
    return choices[0][:-1]


class Command(BaseCommand):
    help = "Seed realistic 30-day analytics data for applications and collections."

    def add_arguments(self, parser):
        parser.add_argument(
            "--app-id",
            type=int,
            help="Specific application ID to seed (default: all apps)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of days to generate history for (default: 30)",
        )
        parser.add_argument(
            "--volume",
            type=str,
            choices=["low", "medium", "high"],
            default="medium",
            help="Data volume multiplier (default: medium)",
        )

    def handle(self, *args, **options):
        days = options.get("days", 30)
        volume = options.get("volume", "medium")
        multiplier = {"low": 0.5, "medium": 1.0, "high": 3.0}.get(volume, 1.0)
        specific_app_id = options.get("app_id")

        self.stdout.write("Checking ClickHouse connection...")
        try:
            client = get_analytics_client(force_enabled=True)
            if not client.ping():
                raise CommandError(
                    "ClickHouse is unreachable on %s:%s. "
                    "Make sure ClickHouse container is running: "
                    "`docker-compose -f docker-compose.dev.yml --profile analytics up -d clickhouse`"
                    % (settings.CLICKHOUSE_HOST, settings.CLICKHOUSE_PORT)
                )
        except AnalyticsUnavailableError as exc:
            raise CommandError(f"ClickHouse client unavailable: {exc}") from exc

        # 1. Ensure tables exist
        schema_dir = Path(settings.BASE_DIR) / "clickhouse" / "tables"
        for sql_file in sorted(schema_dir.glob("*.sql")):
            sql = sql_file.read_text(encoding="utf-8").strip().rstrip(";").strip()
            if sql:
                client.execute(sql)

        # 2. Query target applications
        if specific_app_id:
            apps = list(Application.objects.filter(pk=specific_app_id))
        else:
            apps = list(Application.objects.all())

        if not apps:
            self.stdout.write(self.style.WARNING("No applications found in database to seed."))
        else:
            self.stdout.write(f"Generating analytics for {len(apps)} application(s)...")

        now = datetime.now(timezone.utc)
        total_app_rows = 0

        for app_obj in apps:
            distributions = list(
                Distribution.objects.filter(app=app_obj, deleted__isnull=True).values_list("id", flat=True)
            )
            cat_id = app_obj.categories.values_list("id", flat=True).first()

            rows_to_insert = []
            for day_offset in range(days, -1, -1):
                day_date = now - timedelta(days=day_offset)
                is_weekend = day_date.weekday() in (5, 6)
                base_views = int(random.randint(15, 45) * multiplier * (1.4 if is_weekend else 1.0))

                for _ in range(base_views):
                    hour = random.randint(0, 23)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    event_time = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)

                    os_family, os_ver, os_label = weighted_choice(SAMPLE_OS)
                    (browser_name,) = weighted_choice(SAMPLE_BROWSERS)
                    (country_code,) = weighted_choice(SAMPLE_COUNTRIES)
                    ip_addr = (
                        f"{random.randint(11, 220)}.{random.randint(1, 254)}."
                        f"{random.randint(1, 254)}.{random.randint(1, 254)}"
                    )
                    uid = random.choice([None, None, random.randint(1, 50)])

                    # 1. View event
                    rows_to_insert.append([
                        event_time,
                        "view",
                        int(app_obj.pk),
                        None,
                        cat_id,
                        uid,
                        ip_addr,
                        country_code,
                        os_label,
                        os_ver,
                        browser_name,
                        "",
                        f"sess_{random.randint(1000, 9999)}",
                        "{}",
                    ])

                    # 2. Download event (probability ~25%)
                    if random.random() < 0.25:
                        dist_id = random.choice(distributions) if distributions else None
                        rows_to_insert.append([
                            event_time + timedelta(seconds=random.randint(5, 60)),
                            "download",
                            int(app_obj.pk),
                            dist_id,
                            cat_id,
                            uid,
                            ip_addr,
                            country_code,
                            os_label,
                            os_ver,
                            browser_name,
                            "",
                            f"sess_{random.randint(1000, 9999)}",
                            "{}",
                        ])

                    # 3. Like event (probability ~4%)
                    if random.random() < 0.04:
                        rows_to_insert.append([
                            event_time + timedelta(seconds=random.randint(10, 120)),
                            "like",
                            int(app_obj.pk),
                            None,
                            cat_id,
                            uid or random.randint(1, 50),
                            ip_addr,
                            country_code,
                            os_label,
                            os_ver,
                            browser_name,
                            "",
                            "",
                            json.dumps({"is_like": True}),
                        ])

                    # 4. Rate event (probability ~3%)
                    if random.random() < 0.03:
                        rows_to_insert.append([
                            event_time + timedelta(seconds=random.randint(15, 180)),
                            "rate",
                            int(app_obj.pk),
                            None,
                            cat_id,
                            uid or random.randint(1, 50),
                            ip_addr,
                            country_code,
                            os_label,
                            os_ver,
                            browser_name,
                            "",
                            "",
                            json.dumps({"rating": random.choice([4, 5, 5, 5, 3, 5])}),
                        ])

            if rows_to_insert:
                cols = [
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
                client.insert_rows("analytics_app_events", rows_to_insert, cols)
                total_app_rows += len(rows_to_insert)
                self.stdout.write(f"  -> [{app_obj.title}] Inserted {len(rows_to_insert)} app events")

        # 3. Query target collections
        collections = list(Collection.objects.all())
        total_col_rows = 0
        if collections:
            self.stdout.write(f"Generating analytics for {len(collections)} collection(s)...")
            for col_obj in collections:
                col_rows = []
                for day_offset in range(days, -1, -1):
                    day_date = now - timedelta(days=day_offset)
                    views_count = int(random.randint(5, 20) * multiplier)
                    for _ in range(views_count):
                        hour = random.randint(0, 23)
                        minute = random.randint(0, 59)
                        second = random.randint(0, 59)
                        event_time = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)

                        os_family, os_ver, os_label = weighted_choice(SAMPLE_OS)
                        (browser_name,) = weighted_choice(SAMPLE_BROWSERS)
                        (country_code,) = weighted_choice(SAMPLE_COUNTRIES)
                        ip_addr = (
                            f"{random.randint(11, 220)}.{random.randint(1, 254)}."
                            f"{random.randint(1, 254)}.{random.randint(1, 254)}"
                        )
                        uid = random.choice([None, None, random.randint(1, 50)])

                        col_rows.append([
                            event_time,
                            "view",
                            int(col_obj.pk),
                            col_obj.owner_id,
                            uid,
                            None,
                            1 if getattr(col_obj, "is_system", False) else 0,
                            1 if col_obj.is_public else 0,
                            ip_addr,
                            country_code,
                            os_label,
                            browser_name,
                            "",
                            f"sess_{random.randint(1000, 9999)}",
                            "{}",
                        ])

                        if random.random() < 0.15:
                            col_rows.append([
                                event_time + timedelta(seconds=random.randint(5, 45)),
                                "favorite",
                                int(col_obj.pk),
                                col_obj.owner_id,
                                uid or random.randint(1, 50),
                                None,
                                1 if getattr(col_obj, "is_system", False) else 0,
                                1 if col_obj.is_public else 0,
                                ip_addr,
                                country_code,
                                os_label,
                                browser_name,
                                "",
                                "",
                                json.dumps({"is_favorite": True}),
                            ])

                if col_rows:
                    col_cols = [
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
                    client.insert_rows("analytics_collection_events", col_rows, col_cols)
                    total_col_rows += len(col_rows)
                    self.stdout.write(f"  -> [{col_obj.title}] Inserted {len(col_rows)} collection events")

        # 4. Enable ANALYTICS_ENABLED in Constance
        try:
            config.ANALYTICS_ENABLED = True
            self.stdout.write(self.style.SUCCESS("Enabled config.ANALYTICS_ENABLED = True"))
        except Exception:
            pass

        client.close()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nAnalytics seed completed! Total inserted: {total_app_rows} app events, "
                f"{total_col_rows} collection events."
            )
        )
