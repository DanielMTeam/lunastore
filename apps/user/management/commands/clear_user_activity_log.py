import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.user.models import UserActivityLog 
from django.conf import settings

# User Activity Log (include IPs) clean command (because storage limitation gdpr; we must store data for the shortest time possible)

# in general, sys.admin must configure a cron job or a scheduled task to run this command periodically, e.g., once a week:
# command: python manage.py clear_user_activity_log
class Command(BaseCommand):
    help = f'delete data from UserActivityLog model after {settings.RETENTION_ACTIVITY_LOG_DAYS} days, because of gdpr and storage limitation (we must store data for the shortest time possible)'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - datetime.timedelta(days=settings.RETENTION_ACTIVITY_LOG_DAYS)
        deleted_count, _ = UserActivityLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'[clean_user_activity_log task] successfully deleted {deleted_count} old ips and other data from UserActivityLog model')
        )