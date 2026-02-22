from django.core.management.base import BaseCommand
from django.apps import apps
from django.utils import timezone
from datetime import timedelta
from safedelete.models import SafeDeleteModel, HARD_DELETE

class Command(BaseCommand):
    help = 'Finds all deleted objects across the entire project and removes them permanently'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', 
            type=int, 
            default=30, 
            help='Delete objects that have been in the trash longer than X days (default: 30)'
        )
        parser.add_argument(
            '--all', 
            action='store_true', 
            help='Delete ABSOLUTELY EVERYTHING from the trash right now (ignoring time)'
        )

    def handle(self, *args, **options):
        days = options['days']
        delete_all = options['all']
        threshold_date = timezone.now() - timedelta(days=days)

        total_deleted = 0

        self.stdout.write("Starting database scan for trashed objects...\n")

        for model in apps.get_models():
            if issubclass(model, SafeDeleteModel) and not model._meta.proxy:
                
                if delete_all:
                    trash_qs = model.objects.deleted_only()
                else:
                    trash_qs = model.objects.deleted_only().filter(deleted__lt=threshold_date)

                count = trash_qs.count()
                
                if count > 0:
                    self.stdout.write(f"Cleaning table {model.__name__}... Found objects: {count}")
                    for obj in trash_qs:
                        obj.delete(force_policy=HARD_DELETE)
                        
                    total_deleted += count

        if total_deleted > 0:
            self.stdout.write(self.style.SUCCESS(f'\nSuccess! Permanently deleted objects across the entire database: {total_deleted}'))
        else:
            self.stdout.write(self.style.WARNING('\nTrash is empty, so.. nothing to delete, lmao'))