"""Bounded database search used when Meilisearch is unavailable."""

from django.db.models import Q

from .indexes import APPLICATION_SEARCHABLE, USER_SEARCHABLE


def _text_matches(fields, query):
    condition = Q()
    for field in fields:
        condition |= Q(**{f"{field}__icontains": query})
    return condition


def application_matches(query, *, category_id=None, author_id=None, is_free=False):
    from apps.marketplace.models import Application

    # Preserve the original columns as well as every explicit translation.
    queryset = Application.objects.all().rewrite(False).filter(
        is_private=False, is_under_dmca=False,
    ).filter(_text_matches(APPLICATION_SEARCHABLE, query))
    if category_id is not None:
        queryset = queryset.filter(categories__id=category_id)
    if author_id is not None:
        queryset = queryset.filter(user_id=author_id)
    if is_free:
        queryset = queryset.filter(price=0)
    return queryset.order_by("id")


def user_matches(query):
    from apps.user.models import User

    return User.objects.filter(is_active=True).filter(
        _text_matches(USER_SEARCHABLE, query),
    ).order_by("id")


def page_ids(queryset, *, limit, offset):
    total = queryset.count()
    if offset >= total:
        return [], total
    ids = list(queryset.values_list("id", flat=True)[offset:offset + limit])
    return ids, total


def suggest(query, *, limit, search_type):
    per_index_limit = max(1, limit // 2) if search_type == "all" else limit
    apps = ()
    users = ()
    if search_type in ("all", "apps"):
        apps = application_matches(query)[:per_index_limit]
    if search_type in ("all", "users"):
        users = user_matches(query)[:per_index_limit]
    return format_suggestions(apps, users)


def format_suggestions(apps, users):
    return {
        "apps": [{
            "id": app.pk,
            "title": app.title or "",
            "icon_url": app.icon_url,
            "url": f"/app.php?id={app.pk}",
        } for app in apps],
        "users": [{
            "id": user.pk,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "url": f"/profile.php?id={user.pk}",
        } for user in users],
    }
