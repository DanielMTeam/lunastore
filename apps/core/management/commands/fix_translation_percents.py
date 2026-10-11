import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fix escaped named Python placeholders in local PO translations (%%(name)s -> %(name)s)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report replacements without modifying files.")

    def handle(self, *args, **options):
        pattern = re.compile(r"%%(?=\([^)]+\)[a-zA-Z])")
        total = 0
        for path in sorted((Path(settings.BASE_DIR) / "locale").glob("*/LC_MESSAGES/*.po")):
            content = path.read_bytes().decode("utf-8")
            updated, count = pattern.subn("%", content)
            if not count:
                continue
            if not options["dry_run"]:
                path.write_bytes(updated.encode("utf-8"))
            total += count
            self.stdout.write(f"{path.relative_to(settings.BASE_DIR)}: {count}")
        action = "Found" if options["dry_run"] else "Fixed"
        self.stdout.write(self.style.SUCCESS(f"{action} {total} escaped placeholders."))
