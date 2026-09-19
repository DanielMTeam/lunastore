import logging

from django.core.cache import cache

from apps.core.tasks import send_notification
from apps.marketplace.models import Application, Distribution

logger = logging.getLogger("marketplace")

LUNABOX_REMINDER_CACHE_PREFIX = "lunabox_manifest_reminder_{user_id}_{app_id}"
# remind no more than once a week per app
LUNABOX_REMINDER_COOLDOWN = 7 * 24 * 3600


def notify_unfilled_lunabox_manifests(user):
    """
    Enqueue a notification for each app of the developer that still has
    distributions without a configured lunabox_manifest.

    Only developers of the app are notified. The reminder is throttled per
    app via the cache, so it is not spammed on every page visit.
    """
    if not user or not user.is_authenticated:
        return

    app_ids = list(
        Distribution.objects.filter(
            app__user=user, lunabox_manifest__isnull=True
        ).values_list("app_id", flat=True).distinct())

    for app_id in app_ids:
        cache_key = LUNABOX_REMINDER_CACHE_PREFIX.format(
            user_id=user.id, app_id=app_id)
        try:
            if not cache.add(
                    cache_key, True, timeout=LUNABOX_REMINDER_COOLDOWN):
                continue
        except Exception:
            # if the cache is unavailable, skip instead of spamming users
            logger.exception(
                "lunabox reminder cache unavailable for user=%s app=%s",
                user.id, app_id)
            continue

        try:
            app = Application.objects.get(id=app_id)
            count = Distribution.objects.filter(
                app=app, lunabox_manifest__isnull=True).count()
            send_notification.enqueue(
                user_id=user.id,
                title_key="NOTIF_LUNABOX_MANIFEST_TITLE",
                content_key="NOTIF_LUNABOX_MANIFEST_DESCRIPTION",
                context={"app_name": app.title, "count": count},
                meta={"icon": "help.png"},
            )
        except Application.DoesNotExist:
            logger.warning(
                "lunabox reminder: app %s not found", app_id)
        except Exception:
            logger.exception(
                "lunabox reminder failed for user=%s app=%s",
                user.id, app_id)
