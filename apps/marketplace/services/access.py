"""Application-scoped capabilities and serialized membership changes."""
from functools import partial

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _, gettext_noop

from apps.user.models import User, UserBan
from apps.core.tasks import send_notification
from ..models import (
    Application, ApplicationAccess, AppEditRequests, DistributionCreateRequests, DistributionEditRequests,
)


def user_can_access(user):
    return bool(
        user.is_authenticated and user.is_active and not getattr(user, "deleted", None)
        and User.objects.filter(pk=user.pk, is_active=True).exists()
        and not UserBan.objects.filter(user_id=user.pk).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).exists()
    )


def application_role(app, user):
    if app.deleted or not user_can_access(user):
        return None
    if app.user_id == user.pk:
        return "owner"
    return ApplicationAccess.objects.filter(application=app, user=user).values_list("role", flat=True).first()


def can_manage_app(app, user, capability="info"):
    role = application_role(app, user)
    if capability in ("rights", "community"):
        return role == "owner"
    if capability in ("files", "screenshots", "settings"):
        return role in ("owner", "admin")
    return capability in ("info", "stats", "view") and role in ("owner", "admin", "editor")


def accessible_app_ids(user):
    if not user_can_access(user):
        return Application.objects.none().values("pk")
    return Application.objects.filter(Q(user=user) | Q(access_entries__user=user)).values("pk")


def request_origin(app, user):
    return application_role(app, user) or "community"


@transaction.atomic
def set_application_access(app_id, actor, user, role):
    app = Application.objects.select_for_update().get(pk=app_id)
    if not can_manage_app(app, actor, "rights"):
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))
    if user.pk == app.user_id:
        raise ValidationError(_("ERROR_APP_RIGHTS_OWNER"))
    if role not in ("admin", "editor", "none"):
        raise ValidationError(_("ERROR_APP_RIGHTS_ROLE"))
    if role != "none" and not user_can_access(user):
        raise ValidationError(_("ERROR_APP_RIGHTS_USER"))
    entry = ApplicationAccess.objects.filter(application=app, user=user).first()
    previous = entry.role if entry else "none"
    if previous == role:
        return
    if role == "none":
        if entry:
            entry.delete()
    else:
        ApplicationAccess.objects.update_or_create(
            application=app, user=user, defaults={"role": role, "granted_by": actor},
        )
    origins = ()
    if role == "none":
        origins = ("admin", "editor")
    elif role == "editor":
        origins = ("admin",)
    if origins:
        for model, field in (
            (AppEditRequests, "target_application"),
            (DistributionCreateRequests, "app"),
            (DistributionEditRequests, "app"),
        ):
            model.objects.filter(**{field: app}, user=user, status="pending", request_origin__in=origins).update(
                status="rejected",
            )
    LogEntry.objects.create(
        user=actor, content_type=ContentType.objects.get_for_model(app), object_id=str(app.pk),
        object_repr=str(app), action_flag=CHANGE,
        change_message=f"Application access: user #{user.pk}: {previous} -> {role}",
    )
    if role == "none":
        title_key = gettext_noop("NOTIF_APP_ACCESS_REVOKED_TITLE")
        description = gettext_noop("NOTIF_APP_ACCESS_REVOKED_DESCRIPTION")
    elif previous == "none":
        title_key = gettext_noop("NOTIF_APP_ACCESS_GRANTED_TITLE")
        description = {
            "admin": gettext_noop("NOTIF_APP_ACCESS_GRANTED_ADMIN_DESCRIPTION"),
            "editor": gettext_noop("NOTIF_APP_ACCESS_GRANTED_EDITOR_DESCRIPTION"),
        }[role]
    elif role == "admin":
        title_key = gettext_noop("NOTIF_APP_ACCESS_PROMOTED_TITLE")
        description = gettext_noop("NOTIF_APP_ACCESS_PROMOTED_DESCRIPTION")
    else:
        title_key = gettext_noop("NOTIF_APP_ACCESS_DEMOTED_TITLE")
        description = gettext_noop("NOTIF_APP_ACCESS_DEMOTED_DESCRIPTION")
    # Freeze the event payload now; enqueue only after the outer transaction commits.
    transaction.on_commit(partial(
        send_notification.enqueue,
        user_id=user.pk,
        title_key=title_key,
        content_key=description,
        context={"app_name": str(escape(app.title))},
        meta={"type": "info", "app_id": app.pk, "role": role, "previous_role": previous},
    ), robust=True)
