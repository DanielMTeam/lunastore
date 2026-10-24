from django.contrib import admin
from django.db.models import Count, Min
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.marketplace.models import (
    AppCreateRequests, AppEditRequests, AppReportRequests, Application,
    DistributionCreateRequests, DistributionEditRequests, PendingReview, ProblemReportRequests,
)
from apps.user.models import DevRequestsModel, User
from apps.support.models import Ticket


QUEUES = (
    (AppCreateRequests, _("PAGE_ADMIN_PANEL_NEW_APPLICATIONS"), "add_box", "title"),
    (AppEditRequests, _("PAGE_ADMIN_PANEL_APPLICATION_CHANGES"), "edit", "title"),
    (DistributionCreateRequests, _("PAGE_ADMIN_PANEL_NEW_DISTRIBUTIONS"), "publish", "version"),
    (DistributionEditRequests, _("PAGE_ADMIN_PANEL_DISTRIBUTION_CHANGES"), "edit", "version"),
    (PendingReview, _("PAGE_ADMIN_PANEL_REVIEWS_AWAITING_MODERATION"), "rate_review", "text"),
    (AppReportRequests, _("PAGE_ADMIN_PANEL_APPLICATION_REPORTS"), "report", "description"),
    (Ticket, _("PAGE_SUPPORT_TITLE"), "support_agent", "subject"),
    (DevRequestsModel, _("PAGE_ADMIN_PANEL_DEVELOPER_REQUESTS"), "code", "github"),
)


def queue_badge(request, model):
    model_admin = admin.site._registry[model]
    if not model_admin.has_view_or_change_permission(request):
        return ""
    counts = getattr(request, "_luna_queue_counts", {})
    if model not in counts:
        queryset = model_admin.get_queryset(request)
        if model is Ticket:
            queryset = queryset.filter(status__in=[Ticket.Status.NEW, Ticket.Status.IN_PROGRESS], archived_at__isnull=True)
        elif hasattr(model, "status"):
            queryset = queryset.filter(status="pending")
        if hasattr(model, "deleted"):
            queryset = queryset.filter(deleted__isnull=True)
        counts[model] = queryset.count()
        request._luna_queue_counts = counts
    return str(counts[model]) if counts[model] else ""


def count_appcreaterequests(request):
    return queue_badge(request, AppCreateRequests)


def count_appeditrequests(request):
    return queue_badge(request, AppEditRequests)


def count_distributioncreaterequests(request):
    return queue_badge(request, DistributionCreateRequests)


def count_distributioneditrequests(request):
    return queue_badge(request, DistributionEditRequests)


def count_pendingreview(request):
    return queue_badge(request, PendingReview)


def count_appreportrequests(request):
    return queue_badge(request, AppReportRequests)


def count_support_tickets(request):
    return queue_badge(request, Ticket)


def count_problemreportrequests(request):
    return queue_badge(request, ProblemReportRequests)


def count_devrequestsmodel(request):
    return queue_badge(request, DevRequestsModel)


def callback(request, context):
    queues = []
    oldest = []
    for model, title, icon, preview_field in QUEUES:
        model_admin = admin.site._registry[model]
        if not model_admin.has_view_or_change_permission(request):
            continue
        queryset = model_admin.get_queryset(request)
        has_status = any(field.name == "status" for field in model._meta.fields)
        has_date = any(field.name == "created_at" for field in model._meta.fields)
        if model is Ticket:
            queryset = queryset.filter(status__in=[Ticket.Status.NEW, Ticket.Status.IN_PROGRESS], archived_at__isnull=True)
        elif has_status:
            queryset = queryset.filter(status="pending")
        if hasattr(model, "deleted"):
            queryset = queryset.filter(deleted__isnull=True)
        stats = queryset.aggregate(total=Count("pk"), **({"oldest": Min("created_at")} if has_date else {}))
        if not hasattr(request, "_luna_queue_counts"):
            request._luna_queue_counts = {}
        request._luna_queue_counts[model] = stats["total"]
        model_name = f"{model._meta.app_label}_{model._meta.model_name}"
        url = reverse(f"admin:{model_name}_changelist")
        if model is Ticket:
            url += "?queue=team"
        elif has_status and model is not PendingReview:
            url += "?status__exact=pending"
        queues.append({"title": title, "icon": icon, "count": stats["total"], "url": url,
                       "oldest": stats.get("oldest")})
        if stats["total"]:
            order = ("created_at", "pk") if has_date else ("pk",)
            item = queryset.order_by(*order).first()
            oldest.append({"queue": title, "preview": getattr(item, preview_field) or _("PAGE_ADMIN_PANEL_NO_TEXT"),
                           "created_at": getattr(item, "created_at", None),
                           "url": reverse(f"admin:{model_name}_change", args=[item.pk])})
    oldest.sort(key=lambda item: (item["created_at"] is None, item["created_at"] or timezone.now()))
    statistics = []
    if admin.site._registry[Application].has_view_or_change_permission(request):
        statistics.append({"title": _("PAGE_ADMIN_PANEL_TOTAL_APPLICATIONS"), "value": Application.objects.count()})
    if admin.site._registry[User].has_view_or_change_permission(request):
        statistics.extend([
            {"title": _("PAGE_ADMIN_PANEL_TOTAL_USERS"), "value": User.objects.count()},
            {"title": _("PAGE_ADMIN_PANEL_NEW_TODAY"),
             "value": User.objects.filter(date_joined__date=timezone.localdate()).count()},
        ])
    context.update({"moderation_queues": queues, "oldest_requests": oldest,
                    "pending_total": sum(queue["count"] for queue in queues), "statistics": statistics})
    return context
