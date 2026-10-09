import logging

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.marketplace.models import Application
from apps.user.models import User

from .tasks import sync_application_task, sync_user_task

logger = logging.getLogger(__name__)


def _enqueue_on_commit(task, object_id, using):
    if not settings.MEILISEARCH_ENABLED:
        return

    def enqueue():
        try:
            task.enqueue(object_id, using=using)
        except Exception:
            logger.exception("Failed to enqueue %s for ID %s on %s", task.name, object_id, using)

    transaction.on_commit(enqueue, using=using)


@receiver(post_save, sender=Application)
@receiver(post_delete, sender=Application)
def sync_application_index(sender, instance, using=DEFAULT_DB_ALIAS, raw=False, **kwargs):
    if not raw:
        _enqueue_on_commit(sync_application_task, instance.pk, using)


@receiver(m2m_changed, sender=Application.categories.through)
def sync_application_categories(sender, instance, action, reverse, pk_set, using=DEFAULT_DB_ALIAS, **kwargs):
    if not settings.MEILISEARCH_ENABLED:
        return
    if reverse and action == "pre_clear":
        # post_clear has no pk_set and the relation is already empty by then.
        instance._search_application_ids = list(
            sender.objects.using(using).filter(category_id=instance.pk).values_list("application_id", flat=True)
        )
        return
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not reverse:
        application_ids = [instance.pk]
    elif action == "post_clear":
        application_ids = getattr(instance, "_search_application_ids", [])
        if hasattr(instance, "_search_application_ids"):
            del instance._search_application_ids
    else:
        application_ids = pk_set or ()
    for application_id in application_ids:
        _enqueue_on_commit(sync_application_task, application_id, using)


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def sync_user_index(sender, instance, using=DEFAULT_DB_ALIAS, raw=False, **kwargs):
    if not raw:
        _enqueue_on_commit(sync_user_task, instance.pk, using)
