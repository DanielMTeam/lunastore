from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.core.tasks import send_telegram_notification
from apps.marketplace.models import (
    ProblemReportRequests,
    AppCreateRequests,
    AppEditRequests,
    DistributionCreateRequests,
    DistributionEditRequests
)


@receiver(post_save, sender=ProblemReportRequests)
def notify_about_user_problem_report_in_tg(sender, instance, created, **kwargs):
    if created:
        # check flag
        if not settings.TELEGRAM_LOGGER_ENABLED:
            return

        warning_message = (
            f"⚠️ <b>Юзер прислал проблему:</b>\n\n"
            f"👤 <b>Юзер:</b> {instance.user.username}\n"
            f"🚩 <b>Проблема:</b> {instance.description}"
        )

        send_telegram_notification(warning_message)


@receiver(post_save, sender=AppCreateRequests)
def notify_app_create_request(sender, instance, created, **kwargs):
    if created and getattr(settings, 'TELEGRAM_LOGGER_ENABLED', False):
        message = (
            f"🆕 <b>Новая заявка на публикацию приложения:</b>\n\n"
            f"👤 <b>Автор:</b> {instance.user.username}\n"
            f"📱 <b>Приложение:</b> {instance.title}\n"
        )
        send_telegram_notification(message)

@receiver(post_save, sender=AppEditRequests)
def notify_app_edit_request(sender, instance, created, **kwargs):
    if created and getattr(settings, 'TELEGRAM_LOGGER_ENABLED', False):
        target_title = instance.target_application.title if instance.target_application else "Удаленное приложение"
        message = (
            f"📝 <b>Новая заявка на изменение приложения:</b>\n\n"
            f"👤 <b>Автор:</b> {instance.user.username}\n"
            f"📱 <b>Приложение:</b> {target_title}\n"
        )
        send_telegram_notification(message)

@receiver(post_save, sender=DistributionCreateRequests)
def notify_dist_create_request(sender, instance, created, **kwargs):
    if created and getattr(settings, 'TELEGRAM_LOGGER_ENABLED', False):
        app_title = instance.app.title if instance.app else "Неизвестно"
        message = (
            f"🆕 <b>Новая заявка на публикацию дистрибуции:</b>\n\n"
            f"👤 <b>Автор:</b> {instance.user.username}\n"
            f"📱 <b>Приложение:</b> {app_title} (v{instance.version})\n"
        )
        send_telegram_notification(message)

@receiver(post_save, sender=DistributionEditRequests)
def notify_dist_edit_request(sender, instance, created, **kwargs):
    if created and getattr(settings, 'TELEGRAM_LOGGER_ENABLED', False):
        target_title = "Неизвестно"
        old_version = "Неизвестно"
        if instance.target_distribution:
            target_title = instance.target_distribution.app.title if instance.target_distribution.app else "Неизвестно"
            old_version = instance.target_distribution.version

        message = (
            f"📝 <b>Новая заявка на изменение дистрибуции:</b>\n\n"
            f"👤 <b>Автор:</b> {instance.user.username}\n"
            f"📱 <b>Приложение:</b> {target_title} (v{old_version} -> v{instance.version})\n"
        )
        send_telegram_notification(message)
