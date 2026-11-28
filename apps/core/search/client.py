import logging
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings

logger = logging.getLogger(__name__)

_client = None
_timeout = ContextVar("meilisearch_request_timeout", default=None)


class SearchUnavailableError(Exception):
    # meilisearch disabled or unreachable
    pass


@contextmanager
def search_timeout(seconds):
    token = _timeout.set(seconds)
    try:
        yield
    finally:
        _timeout.reset(token)


def _make_client(timeout):
    import meilisearch

    return meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY or None, timeout=timeout)


def get_meili_client():
    global _client
    if not settings.MEILISEARCH_ENABLED:
        return None
    default_timeout = getattr(settings, "MEILISEARCH_TIMEOUT", 5)
    request_timeout = _timeout.get()
    if request_timeout is not None:
        return _make_client(min(default_timeout, request_timeout))
    if _client is None:
        _client = _make_client(default_timeout)
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
