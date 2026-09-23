from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from apps.core.logger.services import LoggerService
from .tasks import send_telegram_notification
import logging


@receiver(post_save, sender=LogEntry)
def notify_on_admin_action(sender, instance, created, **kwargs):
    logger = logging.getLogger('core')
    logger.warning("im called0")
    if created:
        logger.warning("im called1")
        # check flag
        if not settings.TELEGRAM_LOGGER_ENABLED:
            return

        # check if it is a moderator login log entry
        if "Вход в систему (IP:" in instance.change_message or "Неудачная попытка входа (IP:" in instance.change_message:
            from constance import config
            if not getattr(config, 'TELEGRAM_NOTIFY_MODERATOR_LOGINS', False):
                return

        message = LoggerService.format_log_message(instance)
        send_telegram_notification(message)
