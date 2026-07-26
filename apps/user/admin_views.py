import logging
from typing import Any

from django.contrib import admin, messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render

from apps.user.forms import NoSpamMassScanForm
from apps.user.models import NoSpamRule
from apps.user.services.antispam import AntiSpamService

logger = logging.getLogger("user")

MASS_SCAN_PREVIEW_LIMIT = 200


def _has_mass_action_permission(user: Any, action: str) -> bool:
    if action == NoSpamRule.RuleAction.LOG:
        return user.has_perm("user.view_nospamrule")
    if action == NoSpamRule.RuleAction.BAN:
        return user.has_perm("user.add_userban")
    if action == NoSpamRule.RuleAction.DELETE:
        return user.has_perm("user.delete_user")
    return False


@permission_required("user.view_nospamrule", raise_exception=True)
def admin_nospam_mass_scan(request):
    from apps.user.models import User

    matched_users: list[User] = []
    total_matches = 0
    scan_step = request.POST.get("step", "preview") if request.method == "POST" else "preview"
    form = NoSpamMassScanForm(scan_step=scan_step)

    if request.method == "POST":
        form = NoSpamMassScanForm(request.POST, scan_step=scan_step)
        if form.is_valid():
            match_type = form.cleaned_data["match_type"]
            pattern = form.cleaned_data["pattern"]
            action = form.cleaned_data["action"]
            reason = form.cleaned_data["reason"]

            # deny apply early, before expensive find_users_by_filter
            if scan_step == "apply" and not _has_mass_action_permission(
                request.user, action
            ):
                messages.error(
                    request,
                    "Недостаточно прав для выбранного действия.",
                )
            else:
                try:
                    users_qs, matched_value = AntiSpamService.find_users_by_filter(
                        match_type=match_type,
                        pattern=pattern,
                    )
                except ValueError as exc:
                    logger.warning("invalid noSpam mass scan pattern: %s", exc)
                    form.add_error("pattern", str(exc))
                else:
                    total_matches = users_qs.count()

                    if scan_step == "apply":
                        users_list = list(users_qs)
                        stats = AntiSpamService.apply_mass_action(
                            users=users_list,
                            action=action,
                            reason=reason,
                            matched_value=matched_value,
                            ban_by_ip=form.cleaned_data.get("ban_by_ip", False),
                            is_permanent=form.cleaned_data.get("is_permanent", False),
                            ban_duration_minutes=int(
                                form.cleaned_data.get("ban_duration_minutes") or 60
                            ),
                        )
                        messages.success(
                            request,
                            "Массовая операция завершена: "
                            f"обработано {stats['processed']}, "
                            f"залогировано {stats['logged']}, "
                            f"забанено {stats['banned']}, "
                            f"удалено {stats['deleted']}.",
                        )
                        return redirect("admin_nospam_mass_scan")

                    matched_users = list(
                        users_qs.order_by("-date_joined")[:MASS_SCAN_PREVIEW_LIMIT]
                    )

    context = {
        **admin.site.each_context(request),
        "title": "Массовая проверка noSpam",
        "form": form,
        "matched_users": matched_users,
        "total_matches": total_matches,
        "preview_limit": MASS_SCAN_PREVIEW_LIMIT,
    }
    return render(request, "admin/nospam_mass_scan.html", context)
