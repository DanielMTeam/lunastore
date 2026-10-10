import logging
from functools import wraps
from typing import Optional

from django.conf import settings
from django.db.models import Case, IntegerField, QuerySet, When

from . import fallback
from .client import SearchUnavailableError, get_meili_client
from .documents import (
    application_is_indexable,
    application_to_document,
    user_is_indexable,
    user_to_document,
)
from .indexes import (
    APPLICATIONS_INDEX,
    APPLICATION_INDEX_SETTINGS,
    SUGGEST_APP_ATTRIBUTES,
    SUGGEST_USER_ATTRIBUTES,
    USERS_INDEX,
    USER_INDEX_SETTINGS,
)

logger = logging.getLogger(__name__)

PRIMARY_KEY = "id"
MAX_QUERY_LENGTH = 200
MIN_QUERY_LENGTH = 2
SEARCH_PAGE_SIZE = 10

_indexes_ready = False


def normalize_query(query: Optional[str]) -> str:
    if not query:
        return ""
    return query.strip()[:MAX_QUERY_LENGTH]


def is_query_too_short(query: Optional[str]) -> bool:
    return len(normalize_query(query)) < MIN_QUERY_LENGTH


def parse_is_free(value) -> bool:
    # checkbox "on", api "1" / "true"
    return str(value or "").strip().lower() in ("on", "1", "true")


def parse_optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_total_hits(result: dict, fallback: int = 0) -> int:
    total = result.get("estimatedTotalHits", result.get("totalHits", fallback))
    try:
        return max(int(total), 0)
    except (TypeError, ValueError):
        return fallback


def _meili_operation(func):
    @wraps(func)
    def call(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SearchUnavailableError:
            raise
        except Exception as exc:
            raise SearchUnavailableError(f"Meilisearch {func.__name__} failed: {exc}") from exc
    return call


def _wait_for_task(client, task):
    try:
        client.wait_for_task(
            task.task_uid,
            timeout_in_ms=getattr(settings, "MEILISEARCH_TASK_TIMEOUT_MS", 300000),
        )
    except Exception as exc:
        # A timeout does not cancel the server task. Check once before reporting it.
        try:
            finished = client.get_task(task.task_uid)
        except Exception:
            raise SearchUnavailableError(f"Cannot determine status of Meilisearch task {task.task_uid}") from exc
        if finished.status != "succeeded":
            raise SearchUnavailableError(f"Meilisearch task {task.task_uid}: {finished.status}") from exc
        return finished
    finished = client.get_task(task.task_uid)
    if finished.status != "succeeded":
        raise SearchUnavailableError(
            f"Meilisearch task {task.task_uid}: {finished.status}: {getattr(finished, 'error', None)}"
        )
    return finished


@_meili_operation
def _has_pending_swaps(client):
    if client is None:
        raise SearchUnavailableError("Meilisearch is disabled")
    pending = client.get_tasks({"types": ["indexSwap"], "statuses": ["enqueued", "processing"]})
    return bool(pending.results)


@_meili_operation
def _ensure_index(client, index_uid: str, settings: dict) -> None:
    from meilisearch.errors import MeilisearchApiError

    try:
        index_info = client.get_index(index_uid)
    except MeilisearchApiError as exc:
        if exc.code != "index_not_found":
            raise
        create_task = client.create_index(index_uid, {"primaryKey": PRIMARY_KEY})
        _wait_for_task(client, create_task)
    else:
        if not getattr(index_info, "primary_key", None):
            pk_task = client.index(index_uid).update({"primaryKey": PRIMARY_KEY})
            _wait_for_task(client, pk_task)

    settings_task = client.index(index_uid).update_settings(settings)
    _wait_for_task(client, settings_task)


@_meili_operation
def _add_documents(index, documents: list[dict], *, wait: bool = False) -> None:
    if not documents:
        return
    client = get_meili_client()
    task = index.add_documents(documents, primary_key=PRIMARY_KEY)
    if not wait or client is None:
        return
    _wait_for_task(client, task)


def _ensure_indexes_once() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    SearchService.ensure_indexes()
    _indexes_ready = True


def _build_app_filters(
    *,
    category_id=None,
    author_id=None,
    is_free: bool = False,
) -> list[str]:
    filters = ["is_private = false", "is_under_dmca = false"]
    category_id = parse_optional_int(category_id)
    author_id = parse_optional_int(author_id)
    if category_id is not None:
        filters.append(f"category_ids = {category_id}")
    if author_id is not None:
        filters.append(f"user_id = {author_id}")
    if is_free:
        filters.append("price = 0")
    return filters


def _join_filters(filters: list[str]) -> str:
    return " AND ".join(filters)


def order_queryset_by_ids(queryset: QuerySet, ids: list[int]) -> QuerySet:
    if not ids:
        return queryset.none()
    ordering = Case(
        *[When(pk=pk, then=pos) for pos, pk in enumerate(ids)],
        output_field=IntegerField(),
    )
    return queryset.filter(pk__in=ids).order_by(ordering)


class SearchService:
    @staticmethod
    @_meili_operation
    def ensure_indexes() -> None:
        global _indexes_ready
        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

        _ensure_index(client, APPLICATIONS_INDEX, APPLICATION_INDEX_SETTINGS)
        _ensure_index(client, USERS_INDEX, USER_INDEX_SETTINGS)
        _indexes_ready = True

    @staticmethod
    @_meili_operation
    def index_application(app, *, wait=False) -> None:
        client = get_meili_client()
        if client is None:
            return
        _ensure_indexes_once()
        index = client.index(APPLICATIONS_INDEX)
        if application_is_indexable(app):
            _add_documents(index, [application_to_document(app)], wait=wait)
        else:
            SearchService.delete_application(app.pk, wait=wait)

    @staticmethod
    @_meili_operation
    def delete_application(app_id: int, *, wait=False) -> None:
        client = get_meili_client()
        if client is None:
            return
        _ensure_indexes_once()
        task = client.index(APPLICATIONS_INDEX).delete_document(app_id)
        if wait:
            _wait_for_task(client, task)

    @staticmethod
    @_meili_operation
    def index_user(user, *, wait=False) -> None:
        client = get_meili_client()
        if client is None:
            return
        _ensure_indexes_once()
        index = client.index(USERS_INDEX)
        if user_is_indexable(user):
            _add_documents(index, [user_to_document(user)], wait=wait)
        else:
            SearchService.delete_user(user.pk, wait=wait)

    @staticmethod
    @_meili_operation
    def delete_user(user_id: int, *, wait=False) -> None:
        client = get_meili_client()
        if client is None:
            return
        _ensure_indexes_once()
        task = client.index(USERS_INDEX).delete_document(user_id)
        if wait:
            _wait_for_task(client, task)

    @staticmethod
    def search_application_ids(
        query: str,
        *,
        limit: int = SEARCH_PAGE_SIZE,
        offset: int = 0,
        category_id=None,
        author_id=None,
        is_free: bool = False,
    ) -> tuple[list[int], int]:
        query = normalize_query(query)
        if not query:
            return [], 0

        filters = _build_app_filters(
            category_id=category_id,
            author_id=author_id,
            is_free=is_free,
        )
        search_params = {
            "limit": limit,
            "offset": offset,
            "filter": _join_filters(filters),
        }
        try:
            client = get_meili_client()
            if client is None:
                raise SearchUnavailableError("Meilisearch is disabled")
            result = client.index(APPLICATIONS_INDEX).search(query, search_params)
        except Exception as exc:
            logger.warning("Using database application search: %s", exc)
            return fallback.page_ids(
                fallback.application_matches(
                    query, category_id=parse_optional_int(category_id),
                    author_id=parse_optional_int(author_id), is_free=is_free,
                ),
                limit=limit, offset=offset,
            )

        hits = result.get("hits", [])
        return [hit["id"] for hit in hits], _extract_total_hits(result, len(hits))

    @staticmethod
    def search_user_ids(
        query: str,
        *,
        limit: int = SEARCH_PAGE_SIZE,
        offset: int = 0,
    ) -> tuple[list[int], int]:
        query = normalize_query(query)
        if not query:
            return [], 0

        search_params = {
            "limit": limit,
            "offset": offset,
            "filter": "is_active = true",
        }
        try:
            client = get_meili_client()
            if client is None:
                raise SearchUnavailableError("Meilisearch is disabled")
            result = client.index(USERS_INDEX).search(query, search_params)
        except Exception as exc:
            logger.warning("Using database user search: %s", exc)
            return fallback.page_ids(fallback.user_matches(query), limit=limit, offset=offset)

        hits = result.get("hits", [])
        return [hit["id"] for hit in hits], _extract_total_hits(result, len(hits))

    @staticmethod
    def suggest(
        query: str,
        *,
        limit: int = 8,
        search_type: str = "all",
    ) -> dict:
        query = normalize_query(query)
        if is_query_too_short(query):
            return {"apps": [], "users": []}

        per_index_limit = limit
        if search_type == "all":
            per_index_limit = max(1, limit // 2)

        queries = []
        if search_type in ("all", "apps"):
            queries.append({
                "indexUid": APPLICATIONS_INDEX,
                "q": query,
                "limit": per_index_limit,
                "filter": "is_private = false AND is_under_dmca = false",
                "attributesToRetrieve": SUGGEST_APP_ATTRIBUTES,
            })
        if search_type in ("all", "users"):
            queries.append({
                "indexUid": USERS_INDEX,
                "q": query,
                "limit": per_index_limit,
                "filter": "is_active = true",
                "attributesToRetrieve": SUGGEST_USER_ATTRIBUTES,
            })

        try:
            client = get_meili_client()
            if client is None:
                raise SearchUnavailableError("Meilisearch is disabled")
            response = client.multi_search(queries)
        except Exception as exc:
            logger.warning("Using database search suggestions: %s", exc)
            return fallback.suggest(query, limit=limit, search_type=search_type)

        from apps.marketplace.models import Application
        from apps.user.models import User

        app_ids = []
        user_ids = []
        for result in response.get("results", []):
            index_uid = result.get("indexUid")
            for hit in result.get("hits", []):
                if index_uid == APPLICATIONS_INDEX:
                    app_ids.append(hit["id"])
                elif index_uid == USERS_INDEX:
                    user_ids.append(hit["id"])

        # The index is eventually consistent; visibility and displayed fields
        # must come from the database, including during rebuilds and outages.
        apps = order_queryset_by_ids(
            Application.objects.filter(is_private=False, is_under_dmca=False), app_ids,
        )
        users = order_queryset_by_ids(User.objects.filter(is_active=True), user_ids)
        return fallback.format_suggestions(apps, users)

    @staticmethod
    def order_queryset_by_ids(queryset, ids):
        return order_queryset_by_ids(queryset, ids)

    @staticmethod
    def reindex_applications(queryset=None, batch_size: int = 500) -> int:
        from apps.marketplace.models import Application
        from .reindex import rebuild_index

        if queryset is None:
            queryset = Application.objects.filter(
                is_private=False,
                is_under_dmca=False,
            ).prefetch_related("categories")

        return rebuild_index(
            APPLICATIONS_INDEX, APPLICATION_INDEX_SETTINGS, queryset,
            application_is_indexable, application_to_document, batch_size,
        )

    @staticmethod
    def reindex_users(queryset=None, batch_size: int = 500) -> int:
        from apps.user.models import User
        from .reindex import rebuild_index

        if queryset is None:
            queryset = User.objects.filter(is_active=True)

        return rebuild_index(
            USERS_INDEX, USER_INDEX_SETTINGS, queryset,
            user_is_indexable, user_to_document, batch_size,
        )
