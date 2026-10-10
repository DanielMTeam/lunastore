from django.core.management.base import BaseCommand, CommandError

from apps.core.search.service import SearchService
from apps.core.search.client import SearchUnavailableError


class Command(BaseCommand):
    help = "Reindex applications and users in Meilisearch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--applications",
            action="store_true",
            help="Reindex only applications",
        )
        parser.add_argument(
            "--users",
            action="store_true",
            help="Reindex only users",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Batch size for bulk indexing",
        )

    def handle(self, *args, **options):
        reindex_apps = options["applications"]
        reindex_users = options["users"]
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise CommandError("--batch-size must be positive")

        if not reindex_apps and not reindex_users:
            reindex_apps = True
            reindex_users = True

        try:
            if reindex_apps:
                self.stdout.write("Building and swapping applications index...")
                count = SearchService.reindex_applications(batch_size=batch_size)
                self.stdout.write(self.style.SUCCESS(f"Indexed {count} applications"))

            if reindex_users:
                self.stdout.write("Building and swapping users index...")
                count = SearchService.reindex_users(batch_size=batch_size)
                self.stdout.write(self.style.SUCCESS(f"Indexed {count} users"))
        except SearchUnavailableError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Reindex complete"))
