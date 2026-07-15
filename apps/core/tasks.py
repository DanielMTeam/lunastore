import requests
from django.conf import settings
from django.tasks import task
import logging
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from django.utils import translation
from apps.core.notifications.services import NotificationService

logger = logging.getLogger('core')
User = get_user_model()


def send_telegram_notification(message: str):
    bot_token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_LOG_CHAT_ID
    topic_id = settings.TELEGRAM_LOG_TOPIC_ID

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    # if we have a topic_id, add it to the payload
    if topic_id:
        payload["message_thread_id"] = topic_id

    try:
        requests.post(url, json=payload, timeout=5)
    except requests.RequestException as e:
        logger.error(f"Error sending log to Telegram: {e}")


@task()
def send_notification(
        user_id,
        title_key,
        content_key,
        context=None,
        meta=None):
    """
    :param user_id: id of user
    :param title_key: key from locale
    :param content_key: key from locale
    :param context: context for formatting
    :param meta: meta for notification
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    user_lang = getattr(user, 'language', 'ru')

    with translation.override(user_lang):
        title = _(title_key)
        content = _(content_key)

        if context:
            try:
                content = content % context
            except KeyError as e:
                logging.error(
                    f"Notification formatting error: i can't find key :P; so, you can see log there: {e}")

    # send notification
    NotificationService.send_notification(
        user_id=user.id,
        title=str(title),
        content=str(content),
        meta=meta or {"type": "info"}
    )
