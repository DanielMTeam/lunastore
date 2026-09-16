from apps.marketplace.models import Application
from apps.user.models import User

from .indexes import APP_LANG_SUFFIXES


def _localized_fields(instance, base_fields):
    data = {}
    for field in base_fields:
        for suffix in APP_LANG_SUFFIXES:
            attr = f"{field}{suffix}" if suffix else field
            value = getattr(instance, attr, None)
            if value:
                data[attr] = value
    return data


def application_is_indexable(app: Application) -> bool:
    if app.deleted:
        return False
    if app.is_private:
        return False
    if app.is_under_dmca:
        return False
    return True


def user_is_indexable(user: User) -> bool:
    if user.deleted:
        return False
    if not user.is_active:
        return False
    return True


def application_to_document(app: Application) -> dict:
    category_ids = list(app.categories.values_list("id", flat=True))
    doc = {
        "id": app.pk,
        "user_id": app.user_id,
        "category_ids": category_ids,
        "price": app.price,
        "is_private": app.is_private,
        "is_under_dmca": app.is_under_dmca,
        "title": app.title or "",
        "icon_url": app.icon_url,
    }
    doc.update(_localized_fields(app, ("title", "description", "slogan")))
    if app.original_author:
        doc["original_author"] = app.original_author
    return doc


def user_to_document(user: User) -> dict:
    return {
        "id": user.pk,
        "username": user.username,
        "description": user.description or "",
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
    }
