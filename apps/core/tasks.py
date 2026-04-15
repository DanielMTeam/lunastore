import requests
from django.conf import settings
#from django.tasks import task
import logging

logger = logging.getLogger('core')

#@task
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
