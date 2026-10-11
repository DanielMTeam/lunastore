"""Read-only previews of values applied by the shared moderation services."""

import json

from django.conf import settings
from django.utils.translation import gettext_lazy as _


def display_value(value):
    if value is True:
        return _("PAGE_ADMIN_PANEL_YES")
    if value is False:
        return _("PAGE_ADMIN_PANEL_NO")
    if value is None or value == "" or value == []:
        return _("PAGE_ADMIN_PANEL_NOT_PROVIDED")
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return str(value)


def comparison_rows(obj):
    is_app = hasattr(obj, "target_application")
    target = obj.target_application if is_app else obj.target_distribution
    if target is None:
        return []
    rows = []

    def add(label, current, proposed):
        if current != proposed:
            rows.append({"label": label, "current": display_value(current), "proposed": display_value(proposed)})

    fields = (("original_author", _("PAGE_ADMIN_PANEL_APPLICATION_AUTHOR")), ("price", _("PAGE_ADMIN_PANEL_PRICE")),
              ("is_demo", _("PAGE_ADMIN_PANEL_DEMO_VERSION")), ("is_private", _("PAGE_ADMIN_PANEL_PRIVATE_APPLICATION")),
              ("developer_site", _("PAGE_ADMIN_PANEL_DEVELOPER_WEBSITE"))) if is_app else (
                  ("version", _("PAGE_ADMIN_PANEL_VERSION")), ("url", _("PAGE_ADMIN_PANEL_DOWNLOAD_LINK")),
                  ("lunabox_manifest", _("PAGE_ADMIN_PANEL_LUNABOX_MANIFEST")))
    for field, label in fields:
        add(label, getattr(target, field), getattr(obj, field))
    translated = (("title", _("PAGE_ADMIN_PANEL_TITLE")), ("description", _("PAGE_ADMIN_PANEL_DESCRIPTION")),
                  ("requirements", _("PAGE_ADMIN_PANEL_REQUIREMENTS")), ("slogan", _("PAGE_ADMIN_PANEL_SLOGAN"))) if is_app else (
                      ("changelog", _("PAGE_ADMIN_PANEL_CHANGELOG")),)
    for field, label in translated:
        for code, _language in settings.LANGUAGES:
            name = f"{field}_{code}"
            add(f"{label} ({code})", getattr(target, name), getattr(obj, name))
    if is_app:
        for field, label in (("categories", _("PAGE_ADMIN_PANEL_CATEGORIES")), ("badges", _("PAGE_ADMIN_PANEL_BADGES"))):
            current = sorted(str(item) for item in getattr(target, field).all())
            proposed = sorted(str(item) for item in getattr(obj, field).all())
            add(label, current, proposed)
        if obj.icon_path:
            add(_("PAGE_ADMIN_PANEL_ICON"), target.icon_path, obj.icon_path)
            add(_("PAGE_ADMIN_PANEL_ICON_ID"), target.icon_id, obj.icon_id)
        if obj.screenshots is not None:
            add(_("PAGE_ADMIN_PANEL_SCREENSHOTS"), target.screenshots, obj.screenshots)
    elif obj.cdn_file_id:
        add(_("PAGE_ADMIN_PANEL_CDN_FILE"), target.cdn_file_id, obj.cdn_file_id)
    return rows


class RequestComparisonMixin:
    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        context = dict(extra_context or {})
        if obj and self.has_view_or_change_permission(request, obj):
            context["request_comparison"] = comparison_rows(obj)
        return super().change_view(request, object_id, form_url, extra_context=context)
