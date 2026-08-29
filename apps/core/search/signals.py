import logging

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from apps.marketplace.models import Application
from apps.user.models import User

from .documents import application_is_indexable, user_is_indexable
from .service import SearchService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def sync_application_index(sender, instance, **kwargs):
    try:
        if application_is_indexable(instance):
            SearchService.index_application(instance)
        else:
            SearchService.delete_application(instance.pk)
    except Exception as exc:
        logger.warning("Failed to sync application %s to search index: %s", instance.pk, exc)


@receiver(post_delete, sender=Application)
def remove_application_index(sender, instance, **kwargs):
    try:
        SearchService.delete_application(instance.pk)
    except Exception as exc:
        logger.warning("Failed to remove application %s from search index: %s", instance.pk, exc)


@receiver(m2m_changed, sender=Application.categories.through)
def sync_application_categories(sender, instance, action, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    try:
        if application_is_indexable(instance):
            SearchService.index_application(instance)
    except Exception as exc:
        logger.warning(
            "Failed to sync application %s categories to search index: %s",
            instance.pk,
            exc,
        )


@receiver(post_save, sender=User)
def sync_user_index(sender, instance, **kwargs):
    try:
        if user_is_indexable(instance):
            SearchService.index_user(instance)
        else:
            SearchService.delete_user(instance.pk)
    except Exception as exc:
        logger.warning("Failed to sync user %s to search index: %s", instance.pk, exc)


@receiver(post_delete, sender=User)
def remove_user_index(sender, instance, **kwargs):
    try:
        SearchService.delete_user(instance.pk)
    except Exception as exc:
        logger.warning("Failed to remove user %s from search index: %s", instance.pk, exc)
