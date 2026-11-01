from django import template

from apps.marketplace.models import Application
from apps.marketplace.services.access import application_role, role_has_capability

register = template.Library()


@register.simple_tag(takes_context=True)
def app_capabilities(context, app, user):
    """Reuse presentation data within a request; authorization checks stay uncached."""
    if not app or user is None:
        return {}
    app_id = app.pk if isinstance(app, Application) else app
    request = context.get("request")
    cache = None
    key = (str(app_id), user.pk)
    if request is not None:
        if not hasattr(request, "_app_capabilities_cache"):
            request._app_capabilities_cache = {}
        cache = request._app_capabilities_cache
        if key in cache:
            return cache[key]
    if not isinstance(app, Application):
        app = Application.objects.filter(pk=app).first()
    role = application_role(app, user) if app else None
    capabilities = {name: role_has_capability(role, name) for name in ("info", "files", "rights")}
    capabilities["role"] = role
    if cache is not None:
        cache[key] = capabilities
    return capabilities
