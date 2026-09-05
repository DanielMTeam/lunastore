# assemble rich homepage context (ClickHouse + Postgres + Constance)

from __future__ import annotations

import logging
from typing import Any, Optional

from django.db.models import Avg
from django.http import HttpRequest

from apps.marketplace.models import Application, Category, HomeCategoryBlock

logger = logging.getLogger("marketplace")

HOME_LAYOUT_RICH = "rich"
HOME_LAYOUT_COMPACT = "compact"
VALID_HOME_LAYOUTS = frozenset({HOME_LAYOUT_RICH, HOME_LAYOUT_COMPACT})


def resolve_home_layout(request: HttpRequest) -> str:
    # authenticated user preference wins; guests use cookie; default rich
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        layout = getattr(user, "home_layout", None) or HOME_LAYOUT_RICH
        if layout in VALID_HOME_LAYOUTS:
            return layout
    cookie = request.COOKIES.get("home_layout", "")
    if cookie in VALID_HOME_LAYOUTS:
        return cookie
    return HOME_LAYOUT_RICH


def _public_apps_qs():
    return (
        Application.objects.filter(is_private=False, is_under_dmca=False)
        .select_related("user")
        .prefetch_related("categories", "badges")
        .annotate(cached_avg_rating=Avg("reviews__rating"))
    )


def hydrate_apps_by_ids(app_ids: list[int], *, limit: Optional[int] = None) -> list[Application]:
    # preserve order of app_ids; skip missing/private
    if not app_ids:
        return []
    qs = _public_apps_qs().filter(pk__in=app_ids)
    by_id = {app.pk: app for app in qs}
    ordered: list[Application] = []
    for app_id in app_ids:
        app = by_id.get(app_id)
        if app is not None:
            ordered.append(app)
        if limit is not None and len(ordered) >= limit:
            break
    return ordered


def _fallback_latest_apps(limit: int = 1) -> list[Application]:
    return list(_public_apps_qs().order_by("-published")[:limit])


def get_app_of_the_day() -> Optional[Application]:
    from constance import config

    override_id = int(getattr(config, "HOME_APP_OF_THE_DAY_ID", 0) or 0)
    if override_id > 0:
        apps = hydrate_apps_by_ids([override_id], limit=1)
        if apps:
            return apps[0]

    from apps.analytics.services import get_app_of_the_day_id

    try:
        app_id = get_app_of_the_day_id()
    except Exception:
        logger.exception("get_app_of_the_day_id failed")
        app_id = None

    if app_id:
        apps = hydrate_apps_by_ids([app_id], limit=1)
        if apps:
            return apps[0]

    fallback = _fallback_latest_apps(1)
    return fallback[0] if fallback else None


def get_for_you_apps(user_id: int, *, limit: int = 6) -> list[Application]:
    from apps.analytics.services import get_similar_app_ids

    try:
        ids = get_similar_app_ids(user_id, limit=limit)
    except Exception:
        logger.exception("get_similar_app_ids failed for user_id=%s", user_id)
        return []
    return hydrate_apps_by_ids(ids, limit=limit)


def get_apps_for_category(
    category: Category,
    *,
    limit: int = 4,
    days: int = 30,
) -> list[Application]:
    from apps.analytics.services import get_popular_apps

    popular_ids: list[int] = []
    try:
        popular = get_popular_apps(
            days=days,
            limit=limit * 2,
            event_type="download",
            category_id=category.pk,
        )
        popular_ids = [item["app_id"] for item in popular]
    except Exception:
        logger.exception(
            "get_popular_apps failed for category_id=%s", category.pk
        )

    apps = hydrate_apps_by_ids(popular_ids, limit=limit)
    if len(apps) >= limit:
        return apps[:limit]

    # fill from category by published date
    existing = {app.pk for app in apps}
    fillers = list(
        _public_apps_qs()
        .filter(categories=category)
        .exclude(pk__in=existing)
        .order_by("-published")[: max(0, limit - len(apps))]
    )
    return apps + fillers


def get_editor_choice_block(*, limit: int = 3) -> Optional[dict[str, Any]]:
    from constance import config

    category_id = int(getattr(config, "HOME_EDITOR_CHOICE_CATEGORY_ID", 0) or 0)
    if category_id <= 0:
        return None
    try:
        category = Category.objects.get(pk=category_id)
    except Category.DoesNotExist:
        logger.warning("HOME_EDITOR_CHOICE_CATEGORY_ID=%s not found", category_id)
        return None
    apps = get_apps_for_category(category, limit=limit)
    if not apps:
        return None
    return {"category": category, "apps": apps}


def get_monthly_top_apps(*, limit: int = 4) -> list[Application]:
    from apps.analytics.services import get_popular_apps

    popular_ids: list[int] = []
    try:
        popular = get_popular_apps(days=30, limit=limit * 2, event_type="download")
        popular_ids = [item["app_id"] for item in popular]
    except Exception:
        logger.exception("get_popular_apps monthly failed")

    apps = hydrate_apps_by_ids(popular_ids, limit=limit)
    if len(apps) >= limit:
        return apps[:limit]
    existing = {app.pk for app in apps}
    fillers = list(
        _public_apps_qs()
        .exclude(pk__in=existing)
        .order_by("-published")[: max(0, limit - len(apps))]
    )
    return apps + fillers


def get_category_blocks() -> list[dict[str, Any]]:
    blocks = (
        HomeCategoryBlock.objects.filter(is_enabled=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )
    result: list[dict[str, Any]] = []
    for block in blocks:
        category = block.category
        apps = get_apps_for_category(category, limit=block.apps_limit or 4)
        if not apps:
            continue
        total_count = (
            Application.objects.filter(
                categories=category,
                is_private=False,
                is_under_dmca=False,
            ).count()
        )
        result.append(
            {
                "block": block,
                "category": category,
                "apps": apps,
                "total_count": total_count,
            }
        )
    return result


def build_rich_home_context(request: HttpRequest) -> dict[str, Any]:
    categories = Category.objects.all()
    context: dict[str, Any] = {
        "categories": categories,
        "home_layout": HOME_LAYOUT_RICH,
        "app_of_the_day": get_app_of_the_day(),
        "for_you_apps": [],
        "editor_choice": get_editor_choice_block(limit=3),
        "monthly_top_apps": get_monthly_top_apps(limit=2),
        "category_blocks": get_category_blocks(),
    }
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        context["for_you_apps"] = get_for_you_apps(user.pk, limit=6)
    return context
