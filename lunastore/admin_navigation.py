"""Task-based navigation with explicit active links, independent of Unfold tabs."""

from functools import partial

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def model_active(request, model):
    match = getattr(request, "resolver_match", None)
    return bool(match and match.namespace == "admin" and match.url_name.startswith(f"{model}_"))


def view_active(request, name):
    match = getattr(request, "resolver_match", None)
    return bool(match and match.view_name == name)


def has_permission(request, permission):
    return request.user.has_perm(permission)


def model_permission(request, model, permission):
    # Reuse the actual admin's permission policy, including proxy review permissions.
    from django.contrib import admin

    label = model.replace("_", ".", 1)
    for registered_model, model_admin in admin.site._registry.items():
        if registered_model._meta.label_lower == label:
            return model_admin.has_view_or_change_permission(request)
    return has_permission(request, permission)


def model_link(title, icon, model, permission=None):
    app, name = model.split("_", 1)
    item = {
        "title": title,
        "icon": icon,
        "link": reverse_lazy(f"admin:{model}_changelist"),
        "active": partial(model_active, model=model),
        "permission": partial(model_permission, model=model, permission=permission or f"{app}.view_{name}"),
    }
    if name in ("appcreaterequests", "appeditrequests", "distributioncreaterequests",
                "distributioneditrequests", "pendingreview", "appreportrequests",
                "problemreportrequests", "devrequestsmodel"):
        item["badge"] = f"apps.core.dashboard.count_{name}"
    return item


SIDEBAR = {
    "show_search": True,
    "show_all_applications": False,
    "navigation": [
        {"title": _("PAGE_ADMIN_PANEL_DASHBOARD"), "separator": False, "items": [
            {"title": _("PAGE_ADMIN_PANEL_OVERVIEW"), "icon": "dashboard", "link": reverse_lazy("admin:index"),
             "active": partial(view_active, name="admin:index")},
        ]},
        {"title": _("PAGE_ADMIN_PANEL_MODERATION"), "separator": True, "collapsible": True, "items": [
            model_link(_("PAGE_ADMIN_PANEL_NEW_APPLICATIONS"), "add_box", "marketplace_appcreaterequests"),
            model_link(_("PAGE_ADMIN_PANEL_APPLICATION_CHANGES"), "edit", "marketplace_appeditrequests"),
            model_link(_("PAGE_ADMIN_PANEL_NEW_DISTRIBUTIONS"), "publish", "marketplace_distributioncreaterequests"),
            model_link(_("PAGE_ADMIN_PANEL_DISTRIBUTION_CHANGES"), "edit", "marketplace_distributioneditrequests"),
            model_link(_("PAGE_ADMIN_PANEL_DEVELOPER_REQUESTS"), "code", "user_devrequestsmodel"),
            model_link(_("PAGE_ADMIN_PANEL_REVIEWS_AWAITING_MODERATION"), "pending_actions", "marketplace_pendingreview",
                       "marketplace.view_review"),
            model_link(_("PAGE_ADMIN_PANEL_APPLICATION_REPORTS"), "report", "marketplace_appreportrequests"),
            model_link(_("PAGE_ADMIN_PANEL_PROBLEM_REPORTS"), "flag", "marketplace_problemreportrequests"),
        ]},
        {"title": _("PAGE_ADMIN_PANEL_CATALOG"), "separator": True, "collapsible": True, "items": [
            model_link(_("PAGE_ADMIN_PANEL_APPLICATIONS"), "apps", "marketplace_application"),
            model_link(_("PAGE_ADMIN_PANEL_DISTRIBUTIONS"), "app_registration", "marketplace_distribution"),
            model_link(_("PAGE_ADMIN_PANEL_CATEGORIES"), "category", "marketplace_category"),
            model_link(_("PAGE_ADMIN_PANEL_HOMEPAGE_SECTIONS"), "view_agenda", "marketplace_homecategoryblock"),
            model_link(_("PAGE_ADMIN_PANEL_BADGES"), "local_police", "marketplace_badge"),
            model_link(_("PAGE_ADMIN_PANEL_REVIEWS"), "rate_review", "marketplace_review"),
        ]},
        {"title": _("PAGE_ADMIN_PANEL_USERS"), "separator": True, "collapsible": True, "items": [
            model_link(_("PAGE_ADMIN_PANEL_USERS"), "group", "user_user"),
            model_link(_("PAGE_ADMIN_PANEL_BANS"), "gavel", "user_userban"),
            model_link(_("PAGE_ADMIN_PANEL_GROUPS"), "group", "auth_group"),
            model_link(_("PAGE_ADMIN_PANEL_BLOCKED_USERNAMES"), "person_cancel", "user_blacklistedusername"),
            model_link(_("PAGE_ADMIN_PANEL_INVITATIONS"), "redeem", "user_invitetoken"),
        ]},
        {"title": _("PAGE_ADMIN_PANEL_SECURITY"), "separator": True, "collapsible": True, "items": [
            model_link(_("PAGE_ADMIN_PANEL_NOSPAM_RULES"), "shield", "user_nospamrule"),
            {"title": _("PAGE_ADMIN_PANEL_BULK_SCAN"), "icon": "manage_search",
             "link": reverse_lazy("admin_nospam_mass_scan"),
             "active": partial(view_active, name="admin_nospam_mass_scan"),
             "permission": partial(has_permission, permission="user.view_nospamrule")},
            model_link(_("PAGE_ADMIN_PANEL_NOSPAM_EVENTS"), "history", "user_nospamevent"),
        ]},
        {"title": _("PAGE_ADMIN_PANEL_SETTINGS"), "separator": True, "collapsible": True, "items": [
            model_link(_("PAGE_ADMIN_PANEL_SITE_SETTINGS"), "settings", "constance_config", "constance.change_config"),
            model_link(_("PAGE_ADMIN_PANEL_LEGAL_DOCUMENTS"), "description", "terms_legaldocument"),
            model_link(_("PAGE_ADMIN_PANEL_BANNERS"), "image", "core_banner"),
            {"title": _("PAGE_ADMIN_PANEL_NOTIFICATION_BROADCAST"), "icon": "breaking_news", "link": reverse_lazy("broadcast"),
             "active": partial(view_active, name="broadcast"),
             "permission": lambda request: request.user.is_superuser},
            model_link(_("PAGE_ADMIN_PANEL_ACTIVITY_LOG"), "history", "admin_logentry"),
        ]},
    ],
}
