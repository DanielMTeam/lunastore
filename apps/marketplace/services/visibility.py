from django.db.models import Q


def public_app_filter(prefix=""):
    return Q(**{
        f"{prefix}deleted__isnull": True,
        f"{prefix}is_private": False,
        f"{prefix}is_under_dmca": False,
    })


def can_view_app(app, user):
    from .access import can_manage_app

    return not app.deleted and not app.is_under_dmca and (
        not app.is_private or can_manage_app(app, user, "view")
    )
