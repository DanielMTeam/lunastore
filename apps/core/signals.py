from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from apps.core.logger.services import LoggerService
from .tasks import send_telegram_notification

@receiver(post_save, sender=LogEntry)
def notify_on_admin_action(sender, instance, created, **kwargs):
    if created:
        # check flag
        if not settings.TELEGRAM_LOGGER_ENABLED:
            return

        message = LoggerService.format_log_message(instance)
        send_telegram_notification(message)
