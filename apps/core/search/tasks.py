import logging
import time
from datetime import timedelta

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from django.tasks import task
from django.utils import timezone

from .client import SearchUnavailableError, get_meili_client
from .indexes import APPLICATIONS_INDEX, USERS_INDEX
from .locks import index_write_lock
from .service import SearchService, _has_pending_swaps

logger = logging.getLogger(__name__)
LOCK_RETRY_DELAY = timedelta(seconds=5)


def _sync_record(index_uid, object_id, using):
    if not settings.MEILISEARCH_ENABLED:
        return True
    from apps.marketplace.models import Application
    from apps.user.models import User

    model = Application if index_uid == APPLICATIONS_INDEX else User
    for attempt in range(3):
        try:
            with index_write_lock(index_uid, using=using, blocking=False) as acquired:
                if not acquired:
                    return False
                # A timed-out rebuild releases its DB lock while the server may
                # still swap indexes. Writing before that swap loses the update.
                if _has_pending_swaps(get_meili_client()):
                    return False
                queryset = model.objects.using(using)
                if model is Application:
                    queryset = queryset.prefetch_related("categories")
                instance = queryset.filter(pk=object_id).first()
                if model is Application:
                    if instance is None:
                        SearchService.delete_application(object_id, wait=True)
                    else:
                        SearchService.index_application(instance, wait=True)
                elif instance is None:
                    SearchService.delete_user(object_id, wait=True)
                else:
                    SearchService.index_user(instance, wait=True)
            return True
        except SearchUnavailableError:
            if attempt == 2:
                logger.exception("Search sync failed for %s:%s on %s", index_uid, object_id, using)
                raise
            time.sleep(attempt + 1)


@task()
def sync_application_task(application_id, using=DEFAULT_DB_ALIAS):
    if not _sync_record(APPLICATIONS_INDEX, application_id, using):
        sync_application_task.using(run_after=timezone.now() + LOCK_RETRY_DELAY).enqueue(application_id, using=using)


@task()
def sync_user_task(user_id, using=DEFAULT_DB_ALIAS):
    if not _sync_record(USERS_INDEX, user_id, using):
        sync_user_task.using(run_after=timezone.now() + LOCK_RETRY_DELAY).enqueue(user_id, using=using)
