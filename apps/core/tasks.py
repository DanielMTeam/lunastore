import time
import requests
import html
from django.conf import settings
from django.db import transaction
from django.tasks import task
import logging
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from django.utils import translation
from apps.core.notifications.services import NotificationService

logger = logging.getLogger('core')
User = get_user_model()


# telegram notification task with retries
@task()
def send_telegram_notification_task(
    message: str,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    disable_web_page_preview: bool = True,
) -> bool:
    print("test1")
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_LOG_CHAT_ID", "")
    topic_id = getattr(settings, "TELEGRAM_LOG_TOPIC_ID", None)

    if not bot_token or not chat_id:
        logger.warning(
            "Telegram bot_token or chat_id not configured; skipping notification."
        )
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview,
    }

    # Ensure topic_id is sent as an integer if provided
    if topic_id:
        try:
            payload["message_thread_id"] = int(topic_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid TELEGRAM_LOG_TOPIC_ID format: {topic_id}")

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=5)

            if resp.status_code == 200:
                return True

            # Handle Rate Limiting (429)
            if resp.status_code == 429:
                wait_seconds = 5
                try:
                    params = resp.json().get("parameters", {})
                    wait_seconds = int(params.get("retry_after", 5))
                except Exception:
                    pass

                logger.warning(
                    f"Telegram rate limited (429). Attempt {attempt}/{max_retries}, waiting {wait_seconds}s..."
                )
                if attempt < max_retries:
                    time.sleep(wait_seconds)
                    continue
                return False

            # Handle Bad Formatting (400) - Fall back to plain text
            if (
                resp.status_code == 400
                and "can't parse entities" in resp.text.lower()
            ):
                logger.warning(
                    "Telegram HTML parsing failed. Retrying with plain text escape..."
                )
                payload["text"] = html.escape(message)
                payload.pop("parse_mode", None)
                continue

            # Log other status code failures
            logger.warning(
                f"Telegram sendMessage returned HTTP {resp.status_code} "
                f"(attempt {attempt}/{max_retries}): {resp.text}"
            )

            # Retry on 5xx server errors or transient network failures
            if resp.status_code >= 500 and attempt < max_retries:
                time.sleep(retry_delay * (2 ** (attempt - 1)))
                continue

            return False

        except requests.RequestException as exc:
            logger.warning(
                f"Telegram network exception (attempt {attempt}/{max_retries}): {exc}"
            )
            if attempt < max_retries:
                time.sleep(retry_delay * (2 ** (attempt - 1)))
                continue
            return False

    return False


# enqueue telegram notification after db transaction commits
def send_telegram_notification(message: str):
    def _enqueue():
        try:
            send_telegram_notification_task.enqueue(message)
        except Exception as exc:
            logger.error(f"Failed to enqueue telegram notification: {exc}")
            try:
                send_telegram_notification_task.call(message)
            except Exception as call_exc:
                logger.error(f"Synchronous fallback failed for telegram notification: {call_exc}")

    transaction.on_commit(_enqueue)


# async mass notification delivery
@task()
def broadcast_notification_task(
    user_ids: list[int],
    title: str,
    content: str,
    meta: dict = None,
) -> int:
    if meta is None:
        meta = {"type": "info", "icon": "system.png"}

    delivered_count = 0
    for uid in user_ids:
        try:
            if NotificationService.send_notification(
                user_id=uid,
                title=title,
                content=content,
                meta=meta,
            ):
                delivered_count += 1
        except Exception as exc:
            logger.error(f"Failed to deliver broadcast notification to user {uid}: {exc}")

    logger.info(f"Broadcast notification completed: delivered {delivered_count}/{len(user_ids)}")
    return delivered_count


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
