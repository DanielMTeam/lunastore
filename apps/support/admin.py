from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from . import services
from .forms import StaffMessageForm, StaffTicketForm
from .models import Attachment, Delivery, Message, ReadReceipt, Ticket
from .storage import download_url, stage_uploads
from .views import message_page


class QueueFilter(admin.SimpleListFilter):
    title = _('ADMIN_SUPPORT_QUEUE')
    parameter_name = 'queue'

    def lookups(self, request, model_admin):
        return [('new', _('ADMIN_SUPPORT_QUEUE_NEW')), ('unassigned', _('ADMIN_SUPPORT_QUEUE_UNASSIGNED')), ('mine', _('ADMIN_SUPPORT_QUEUE_MINE')),
                ('team', _('ADMIN_SUPPORT_QUEUE_WAITING_TEAM')), ('unread', _('ADMIN_SUPPORT_QUEUE_UNREAD'))]

    def queryset(self, request, queryset):
        active = queryset.filter(archived_at__isnull=True).exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.SPAM])
        if self.value() == 'new':
            return active.filter(status=Ticket.Status.NEW)
        if self.value() == 'unassigned':
            return active.filter(assignee__isnull=True)
        if self.value() == 'mine':
            return active.filter(assignee=request.user)
        if self.value() == 'team':
            return active.filter(status__in=[Ticket.Status.NEW, Ticket.Status.IN_PROGRESS])
        if self.value() == 'unread':
            return queryset.filter(last_customer_message_id__gt=F('staff_read_id'))
        return queryset


@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = ['id', 'subject', 'owner', 'status', 'priority', 'assignee', 'updated_at', 'unread']
    list_filter = [QueueFilter, 'status', 'priority', 'category', 'assignee', 'archived_at']
    search_fields = ['=id', 'subject', 'owner__username']
    list_per_page = 30
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return services.can_view_staff(request.user)

    def has_change_permission(self, request, obj=None):
        return services.can_process(request.user)

    def get_queryset(self, request):
        receipt = ReadReceipt.objects.filter(ticket_id=OuterRef('pk'), staff=request.user).values('last_message_id')[:1]
        return super().get_queryset(request).select_related('owner', 'assignee').annotate(
            staff_read_id=Coalesce(Subquery(receipt), Value(0)))

    @admin.display(boolean=True, description=_('ADMIN_SUPPORT_UNREAD'))
    def unread(self, obj):
        return obj.last_customer_message_id > obj.staff_read_id

    def get_urls(self):
        return [
            path('<int:object_id>/updates/', self.admin_site.admin_view(self.updates), name='support_ticket_updates'),
            path('attachment/<int:attachment_id>/', self.admin_site.admin_view(self.attachment),
                 name='support_attachment_download'),
        ] + super().get_urls()

    def updates(self, request, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        if request.method != 'GET':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET'])
        row = get_object_or_404(Ticket, pk=object_id)
        return JsonResponse({'revision': row.staff_revision})

    def attachment(self, request, attachment_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        if request.method != 'GET':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET'])
        row = get_object_or_404(Attachment, pk=attachment_id, message__isnull=False, file_id__isnull=False)
        response = redirect(download_url(row.file_id, request))
        response['Referrer-Policy'] = 'no-referrer'
        return response

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied
        if request.method not in ('GET', 'POST'):
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET', 'POST'])
        ticket = get_object_or_404(Ticket.objects.select_related('owner', 'assignee'), pk=object_id if str(object_id).isdigit() else 0)
        action = request.POST.get('action')
        reply_form = StaffMessageForm(
            request.POST if request.method == 'POST' and action != 'settings' else None, request.FILES or None,
        )
        settings_form = StaffTicketForm(request.POST if request.method == 'POST' and action == 'settings' else None,
                                        initial={'status': ticket.status, 'priority': ticket.priority,
                                                 'assignee': ticket.assignee_id})
        if request.method == 'POST':
            if not self.has_change_permission(request):
                raise PermissionDenied
            if action == 'settings' and settings_form.is_valid():
                try:
                    values = settings_form.cleaned_data
                    services.update_ticket(ticket.pk, request.user, status=values['status'], priority=values['priority'],
                                           assignee_id=values['assignee'].pk if values['assignee'] else None, staff=True)
                    self.log_change(request, ticket, 'Support ticket settings updated')
                    return redirect(request.path)
                except ValidationError as exc:
                    settings_form.add_error(None, exc)
            elif action in ('reply', 'resolve', 'note') and reply_form.is_valid():
                try:
                    if ticket.archived_at:
                        raise ValidationError(_('ERROR_SUPPORT_ARCHIVED_READ_ONLY'))
                    data = reply_form.cleaned_data
                    exists = Message.objects.filter(ticket=ticket, author=request.user, request_key=data['request_key'])
                    if not exists.exists():
                        ids = stage_uploads(request.user, reply_form.uploads())
                        services.reply(ticket.pk, request.user, data['body'], data['request_key'], ids, staff=True,
                                       internal=action == 'note', resolve=action == 'resolve')
                        self.log_change(request, ticket, 'Support internal note added' if action == 'note'
                                        else 'Support reply sent')
                    return redirect(request.path)
                except ValidationError as exc:
                    reply_form.add_error(None, exc)
            elif action not in ('settings', 'reply', 'resolve', 'note'):
                raise PermissionDenied
        page = message_page(ticket, request, staff=True)
        event_page = Paginator(ticket.events.select_related('actor').order_by('-pk'), 20).get_page(
            request.GET.get('event_page'))
        context = dict(self.admin_site.each_context(request), opts=self.model._meta,
                       title=str(ticket), original=ticket, ticket=ticket, page_obj=page,
                       form=reply_form, settings_form=settings_form,
                       can_reply=self.has_change_permission(request) and not ticket.archived_at,
                       poll_url=reverse('admin:support_ticket_updates', args=[ticket.pk]), revision=ticket.staff_revision,
                       refresh_url=reverse('admin:support_ticket_change', args=[ticket.pk]) + '?fragment=1',
                       support_staff=True,
                       events=event_page.object_list, event_page=event_page,
                       is_popup=False, has_view_permission=True, has_change_permission=self.has_change_permission(request))
        template = ('support/thread_fragment.html' if request.method == 'GET' and request.GET.get('fragment') == '1'
                    else 'admin/support/ticket.html')
        return TemplateResponse(request, template, context)


@admin.register(Delivery)
class DeliveryAdmin(ModelAdmin):
    list_display = ['id', 'event', 'channel', 'state', 'attempts', 'available_at', 'last_error']
    list_filter = ['state', 'channel']
    list_select_related = ['event']
    readonly_fields = [field.name for field in Delivery._meta.fields]
    actions = ['retry_delivery']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return services.can_view_staff(request.user)

    def has_change_permission(self, request, obj=None):
        return services.can_process(request.user)

    @admin.action(description=_('ADMIN_SUPPORT_RETRY_DELIVERIES'), permissions=['change'])
    def retry_delivery(self, request, queryset):
        from django.db import transaction
        from functools import partial
        if not services.can_process(request.user):
            raise PermissionDenied
        with transaction.atomic():
            rows = list(queryset.select_for_update().filter(state__in=[Delivery.State.FAILED, Delivery.State.SKIPPED]))
            for row in rows:
                row.state = Delivery.State.PENDING
                row.attempts = 0
                row.available_at = timezone.now()
                row.last_error = ''
                row.lease_token = None
                row.save()
                transaction.on_commit(partial(services._wake, row.pk))
        self.message_user(request, _('ADMIN_SUPPORT_DELIVERIES_QUEUED'), messages.SUCCESS)
