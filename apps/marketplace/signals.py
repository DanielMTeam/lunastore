from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.tasks import send_telegram_notification
from apps.marketplace.models import ProblemReportRequests


@receiver(post_save, sender=ProblemReportRequests)
def notify_about_user_problem_report_in_tg(sender, instance, created, **kwargs):
    if created:
        # check flag
        if not settings.TELEGRAM_LOGGER_ENABLED:
            return

        warning_message = (
            f"⚠️ <b>Юзер прислал проблему:</b>\n\n"
            f"👤 <b>Юзер:</b> {instance.user.id}\n"
            f"🚩 <b>Проблема:</b> {instance.description}"
        )

        send_telegram_notification(warning_message)
