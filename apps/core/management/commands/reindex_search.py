from django.core.management.base import BaseCommand

from apps.core.search.service import SearchService


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

        if not reindex_apps and not reindex_users:
            reindex_apps = True
            reindex_users = True

        self.stdout.write("Updating Meilisearch index settings...")
        SearchService.ensure_indexes()

        if reindex_apps:
            self.stdout.write("Reindexing applications...")
            count = SearchService.reindex_applications(batch_size=batch_size)
            self.stdout.write(self.style.SUCCESS(f"Indexed {count} applications"))

        if reindex_users:
            self.stdout.write("Reindexing users...")
            count = SearchService.reindex_users(batch_size=batch_size)
            self.stdout.write(self.style.SUCCESS(f"Indexed {count} users"))

        self.stdout.write(self.style.SUCCESS("Reindex complete"))
