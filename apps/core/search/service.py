import logging
from typing import Optional

from django.db.models import Case, IntegerField, QuerySet, When

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


def _ensure_index(client, index_uid: str, settings: dict) -> None:
    try:
        index_info = client.get_index(index_uid)
        if not getattr(index_info, "primary_key", None):
            pk_task = client.index(index_uid).update({"primaryKey": PRIMARY_KEY})
            client.wait_for_task(pk_task.task_uid)
    except Exception:
        create_task = client.create_index(index_uid, {"primaryKey": PRIMARY_KEY})
        client.wait_for_task(create_task.task_uid)

    settings_task = client.index(index_uid).update_settings(settings)
    client.wait_for_task(settings_task.task_uid)


def _add_documents(index, documents: list[dict], *, wait: bool = False) -> None:
    if not documents:
        return
    client = get_meili_client()
    task = index.add_documents(documents, primary_key=PRIMARY_KEY)
    if not wait or client is None:
        return
    client.wait_for_task(task.task_uid)
    finished = client.get_task(task.task_uid)
    if getattr(finished, "status", None) == "failed":
        raise SearchUnavailableError(
            f"Meilisearch indexing failed: {getattr(finished, 'error', finished)}"
        )


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
    def ensure_indexes() -> None:
        global _indexes_ready
        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

        _ensure_index(client, APPLICATIONS_INDEX, APPLICATION_INDEX_SETTINGS)
        _ensure_index(client, USERS_INDEX, USER_INDEX_SETTINGS)
        _indexes_ready = True

    @staticmethod
    def index_application(app) -> None:
        client = get_meili_client()
        if client is None:
            return
        try:
            _ensure_indexes_once()
        except SearchUnavailableError as exc:
            logger.warning("Search indexes unavailable, skip app %s: %s", app.pk, exc)
            return
        index = client.index(APPLICATIONS_INDEX)
        if application_is_indexable(app):
            _add_documents(index, [application_to_document(app)], wait=False)
        else:
            SearchService.delete_application(app.pk)

    @staticmethod
    def delete_application(app_id: int) -> None:
        client = get_meili_client()
        if client is None:
            return
        try:
            client.index(APPLICATIONS_INDEX).delete_document(app_id)
        except Exception as exc:
            logger.warning("Failed to delete application %s from index: %s", app_id, exc)

    @staticmethod
    def index_user(user) -> None:
        client = get_meili_client()
        if client is None:
            return
        try:
            _ensure_indexes_once()
        except SearchUnavailableError as exc:
            logger.warning("Search indexes unavailable, skip user %s: %s", user.pk, exc)
            return
        index = client.index(USERS_INDEX)
        if user_is_indexable(user):
            _add_documents(index, [user_to_document(user)], wait=False)
        else:
            SearchService.delete_user(user.pk)

    @staticmethod
    def delete_user(user_id: int) -> None:
        client = get_meili_client()
        if client is None:
            return
        try:
            client.index(USERS_INDEX).delete_document(user_id)
        except Exception as exc:
            logger.warning("Failed to delete user %s from index: %s", user_id, exc)

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

        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

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
            result = client.index(APPLICATIONS_INDEX).search(query, search_params)
        except Exception as exc:
            logger.error("Meilisearch application search failed: %s", exc, exc_info=True)
            raise SearchUnavailableError("Search service unavailable") from exc

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

        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

        search_params = {
            "limit": limit,
            "offset": offset,
            "filter": "is_active = true",
        }
        try:
            result = client.index(USERS_INDEX).search(query, search_params)
        except Exception as exc:
            logger.error("Meilisearch user search failed: %s", exc, exc_info=True)
            raise SearchUnavailableError("Search service unavailable") from exc

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
        if not query:
            return {"apps": [], "users": []}

        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

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
            response = client.multi_search(queries)
        except Exception as exc:
            logger.error("Meilisearch suggest failed: %s", exc, exc_info=True)
            raise SearchUnavailableError("Search service unavailable") from exc

        apps = []
        users = []
        for result in response.get("results", []):
            index_uid = result.get("indexUid")
            for hit in result.get("hits", []):
                if index_uid == APPLICATIONS_INDEX:
                    apps.append({
                        "id": hit["id"],
                        "title": hit.get("title", ""),
                        "icon_url": hit.get("icon_url", ""),
                        "url": f"/app.php?id={hit['id']}",
                    })
                elif index_uid == USERS_INDEX:
                    users.append({
                        "id": hit["id"],
                        "username": hit.get("username", ""),
                        "avatar_url": hit.get("avatar_url", ""),
                        "url": f"/profile.php?id={hit['id']}",
                    })

        return {"apps": apps, "users": users}

    @staticmethod
    def order_queryset_by_ids(queryset, ids):
        return order_queryset_by_ids(queryset, ids)

    @staticmethod
    def reindex_applications(queryset=None, batch_size: int = 500) -> int:
        from apps.marketplace.models import Application

        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

        if queryset is None:
            queryset = Application.objects.filter(
                is_private=False,
                is_under_dmca=False,
            ).prefetch_related("categories")

        docs = []
        count = 0
        index = client.index(APPLICATIONS_INDEX)
        delete_task = index.delete_all_documents()
        client.wait_for_task(delete_task.task_uid)
        for app in queryset.iterator(chunk_size=batch_size):
            if not application_is_indexable(app):
                continue
            docs.append(application_to_document(app))
            if len(docs) >= batch_size:
                _add_documents(index, docs, wait=True)
                count += len(docs)
                docs = []
        if docs:
            _add_documents(index, docs, wait=True)
            count += len(docs)
        return count

    @staticmethod
    def reindex_users(queryset=None, batch_size: int = 500) -> int:
        from apps.user.models import User

        client = get_meili_client()
        if client is None:
            raise SearchUnavailableError("Meilisearch is disabled")

        if queryset is None:
            queryset = User.objects.filter(is_active=True)

        docs = []
        count = 0
        index = client.index(USERS_INDEX)
        delete_task = index.delete_all_documents()
        client.wait_for_task(delete_task.task_uid)
        for user in queryset.iterator(chunk_size=batch_size):
            if not user_is_indexable(user):
                continue
            docs.append(user_to_document(user))
            if len(docs) >= batch_size:
                _add_documents(index, docs, wait=True)
                count += len(docs)
                docs = []
        if docs:
            _add_documents(index, docs, wait=True)
            count += len(docs)
        return count
