import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


class SearchUnavailableError(Exception):
    # meilisearch disabled or unreachable
    pass


def get_meili_client():
    global _client
    if not settings.MEILISEARCH_ENABLED:
        return None
    if _client is None:
        import meilisearch

        _client = meilisearch.Client(
            settings.MEILISEARCH_URL,
            settings.MEILISEARCH_MASTER_KEY or None,
        )
    return _client


def is_search_available() -> bool:
    if not settings.MEILISEARCH_ENABLED:
        return False
    try:
        client = get_meili_client()
        if client is None:
            return False
        client.health()
        return True
    except Exception as exc:
        logger.warning("Meilisearch health check failed: %s", exc)
        return False
