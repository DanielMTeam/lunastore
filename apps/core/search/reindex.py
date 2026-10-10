import logging
from uuid import uuid4

from .client import SearchUnavailableError, get_meili_client
from .locks import index_write_lock
from .service import PRIMARY_KEY, _add_documents, _ensure_index, _has_pending_swaps, _meili_operation, _wait_for_task

logger = logging.getLogger(__name__)


@_meili_operation
def rebuild_index(index_uid, index_settings, queryset, is_indexable, to_document, batch_size):
    if batch_size <= 0:
        raise SearchUnavailableError("Search batch size must be positive")
    client = get_meili_client()
    if client is None:
        raise SearchUnavailableError("Meilisearch is disabled")
    temp_uid = f"{index_uid}_rebuild_{uuid4().hex}"
    with index_write_lock(index_uid, using=queryset.db):
        # A previous timed-out swap may still be running. Never overtake it.
        if _has_pending_swaps(client):
            raise SearchUnavailableError("A Meilisearch index swap is still pending; retry reindex later")
        swap_started = False
        try:
            _wait_for_task(client, client.create_index(temp_uid, {"primaryKey": PRIMARY_KEY}))
            _wait_for_task(client, client.index(temp_uid).update_settings(index_settings))
            index = client.index(temp_uid)
            docs = []
            count = 0
            for instance in queryset.iterator(chunk_size=batch_size):
                if not is_indexable(instance):
                    continue
                docs.append(to_document(instance))
                if len(docs) >= batch_size:
                    _add_documents(index, docs, wait=True)
                    count += len(docs)
                    docs = []
            if docs:
                _add_documents(index, docs, wait=True)
                count += len(docs)
            # Ensure the live UID exists for the first deployment, only after the
            # replacement is ready. Searches keep using its existing documents.
            _ensure_index(client, index_uid, index_settings)
            swap_started = True
            swap_task = client.swap_indexes([{"indexes": [index_uid, temp_uid]}])
            _wait_for_task(client, swap_task)
        except Exception:
            if not swap_started:
                _cleanup_index(client, temp_uid)
            else:
                logger.exception("Swap outcome requires inspection; retaining index %s", temp_uid)
            raise
        _cleanup_index(client, temp_uid)
        return count


def _cleanup_index(client, index_uid):
    try:
        _wait_for_task(client, client.delete_index(index_uid))
    except Exception:
        logger.exception("Could not clean up search index %s", index_uid)
