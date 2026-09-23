from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.logger.services import LoggerService
from .tasks import send_telegram_notification


@receiver(post_save, sender=LogEntry)
def notify_on_admin_action(sender, instance, created, **kwargs):
    if not created:
        return

    # Check settings flag
    telegram_enabled = getattr(settings, 'TELEGRAM_LOGGER_ENABLED', False)
    if not telegram_enabled:
        return

    # Check moderator login message match
    change_msg = instance.change_message or ''
    is_login_event = (
        'Вход в систему (IP:' in change_msg
        or 'Неудачная попытка входа (IP:' in change_msg
    )

    if is_login_event:
        from constance import config

        notify_mod = getattr(config, 'TELEGRAM_NOTIFY_MODERATOR_LOGINS', False)
        if not notify_mod:
            return

    message = LoggerService.format_log_message(instance)

    # send_telegram_notification enqueues the task after the DB transaction commits
    send_telegram_notification(message)
