from django import template

from apps.marketplace.models import Application
from apps.marketplace.services.access import application_role

register = template.Library()


@register.simple_tag
def app_capabilities(app, user):
    if not app or user is None:
        return {}
    if not isinstance(app, Application):
        app = Application.objects.filter(pk=app).first()
    role = application_role(app, user) if app else None
    return {
        "role": role, "info": role in ("owner", "admin", "editor"),
        "files": role in ("owner", "admin"), "rights": role == "owner",
    }
