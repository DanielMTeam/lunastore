"""Owner-only HTML forms for application membership."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django_smart_ratelimit import ratelimit

from apps.user.decorators import require_modern_browser
from apps.user.models import User
from .forms import ApplicationAccessForm
from .models import Application
from .services.access import can_manage_app, set_application_access


@login_required
@require_modern_browser
@require_http_methods(["GET", "POST"])
@csrf_protect
@ratelimit(key="user", rate="20/3m", block=True)
def application_rights(request, pk, user_id=None, add=False):
    app = get_object_or_404(Application, pk=pk)
    if not can_manage_app(app, request.user, "rights"):
        raise PermissionDenied(_("ERROR_YOURE_NOT_OWNER_OF_APP"))
    entries = app.access_entries.select_related("user").filter(user__deleted__isnull=True).order_by("user__username")
    target = get_object_or_404(User, pk=user_id) if user_id is not None else None
    if target is not None and target.pk == app.user_id:
        raise PermissionDenied(_("ERROR_APP_RIGHTS_OWNER"))
    editing = add or target is not None
    current = app.access_entries.filter(user=target).first() if target else None
    form = ApplicationAccessForm(
        request.POST if request.method == "POST" else None, target_user=target,
        initial={"role": current.role if current else "editor"},
    ) if editing else None
    if request.method == "POST":
        if not editing:
            raise PermissionDenied
        if form.is_valid():
            try:
                set_application_access(app.pk, request.user, form.target_user, form.cleaned_data["role"])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _("PAGE_ADMIN_APP_RIGHTS_SAVED"))
                return redirect("app_rights", pk=app.pk)
    return render(request, "admin_app_rights_edit.html" if editing else "admin_app_rights.html", {
        "app": app, "obj": app, "entries": entries, "participant_count": entries.count() + 1,
        "form": form, "target_user": target, "current_entry": current,
        "app_id": app.pk, "developer_id": app.user_id, "developer_site": app.developer_site,
        "is_edit_page": True,
    })
