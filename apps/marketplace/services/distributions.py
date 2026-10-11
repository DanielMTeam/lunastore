"""Shared permissions and upload configuration for community distributions."""

from django.conf import settings
from django.urls import reverse


def can_submit_community_distribution(app, user):
    return (
        user.is_authenticated
        and user.is_active
        and not user.deleted
        and not app.is_private
        and not app.is_under_dmca
        and app.allow_community_distributions
        and (user.is_superuser or user.groups.filter(name="Разработчики").exists())
    )


def community_request_is_current(req, app, target=None):
    if req.user_id == app.user_id:
        return True
    if app.deleted or not can_submit_community_distribution(app, req.user):
        return False
    return target is None or (not target.deleted and target.published <= req.created_at)


def distribution_upload_context(request):
    spire_url = getattr(request, "geo_domains", {}).get("SPIRE_URL", settings.LUNASPIRE_URL)
    return {
        "get_token_url": reverse("user-get-private-upload-token"),
        "cdn_upload_url": f"{spire_url.rstrip('/')}/cdn/upload",
    }
