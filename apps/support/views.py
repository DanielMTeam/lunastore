from functools import wraps

from constance import config
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django_smart_ratelimit import ratelimit

from apps.core.utils import get_client_ip
from apps.user.middleware import BlockBannedIP
from apps.user.models import UserBan
from apps.user.services.antispam import AntiSpamService, NoSpamContext
from . import services
from .forms import ChatMessageForm, TicketForm
from .models import Attachment, Message, Ticket
from .storage import download_url, stage_uploads


def ip_key(request, *args, **kwargs):
    return f'support:ip:{request.path}:{get_client_ip(request)}'


def user_key(request, *args, **kwargs):
    return f'support:user:{request.path}:{request.user.pk}'


def support_access(view):
    @login_required
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not config.SUPPORT_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)
    return wrapped


def guard_write(request, entrypoint):
    ip = get_client_ip(request)
    active = Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
    if (ip in BlockBannedIP.get_banned_set()
            or UserBan.objects.filter(active, user=request.user).exists()):
        raise PermissionDenied
    context = NoSpamContext(entrypoint=entrypoint, user=request.user, username=request.user.username,
                            email=request.user.email, ip=ip, user_agent=request.META.get('HTTP_USER_AGENT', ''))
    try:
        decision = AntiSpamService.evaluate_and_apply(context=context, target_user=request.user)
    except Exception:
        if str(config.NOSPAM_FAIL_MODE).lower() == 'deny':
            raise PermissionDenied
    else:
        if decision and decision.should_block:
            raise PermissionDenied


def owner_ticket(request):
    return get_object_or_404(Ticket.objects.select_related('owner', 'assignee'),
                             pk=request.GET.get('id') if str(request.GET.get('id', '')).isdigit() else 0,
                             owner=request.user)


def message_page(ticket, request, staff=False):
    qs = ticket.messages.select_related('author').prefetch_related('attachments').order_by('pk')
    if not staff:
        qs = qs.filter(internal=False)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page') or paginator.num_pages)
    # Evaluate this exact page before advancing cursors, so concurrent arrivals stay unread.
    list(page.object_list)
    services.mark_read(ticket, request.user, page.object_list, staff=staff)
    return page


@support_access
@require_GET
def ticket_list(request):
    tickets = Ticket.objects.filter(owner=request.user).select_related('assignee').order_by('-public_updated_at', '-pk')
    if request.GET.get('view') == 'open':
        tickets = tickets.filter(archived_at__isnull=True).exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.SPAM])
    elif request.GET.get('view') == 'unread':
        tickets = tickets.filter(last_staff_message_id__gt=F('owner_read_message_id'))
    return render(request, 'support/list.html', {
        'page_obj': Paginator(tickets, 20).get_page(request.GET.get('page')),
        'filter_view': request.GET.get('view', ''),
    })


@support_access
@require_http_methods(['GET', 'POST'])
@ratelimit(key=ip_key, rate='20/1m', block=True, skip_if=lambda request: request.method != 'POST')
@ratelimit(key=user_key, rate='5/1h', block=True, skip_if=lambda request: request.method != 'POST')
def ticket_create(request):
    form = TicketForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST':
        guard_write(request, 'support_create')
        if form.is_valid():
            existing = Ticket.objects.filter(owner=request.user, request_key=form.cleaned_data['request_key']).first()
            if existing:
                return redirect(ticket_url(existing.pk))
            try:
                ids = stage_uploads(request.user, form.uploads())
                ticket = services.create_ticket(request.user, form.cleaned_data, ids)
                return redirect(ticket_url(ticket.pk))
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, 'support/create.html', {'form': form})


def ticket_url(ticket_id):
    return reverse('support:detail') + f'?id={ticket_id}'


def render_ticket(request, ticket, form=None, status=200):
    page = message_page(ticket, request)
    template = ('support/thread_fragment.html' if request.method == 'GET' and request.GET.get('fragment') == '1'
                else 'support/detail.html')
    return render(request, template, {
        'ticket': ticket, 'page_obj': page, 'form': form if form is not None else ChatMessageForm(),
        'can_reply': ticket.archived_at is None and ticket.status != Ticket.Status.SPAM,
        'poll_url': reverse('support:updates') + f'?id={ticket.pk}', 'revision': ticket.public_revision,
        'refresh_url': ticket_url(ticket.pk) + '&fragment=1',
    }, status=status)


@support_access
@require_GET
def ticket_detail(request):
    return render_ticket(request, owner_ticket(request))


@support_access
@require_POST
@ratelimit(key=ip_key, rate='20/1m', block=True)
@ratelimit(key=user_key, rate='10/1m', block=True)
def ticket_reply(request):
    ticket = owner_ticket(request)
    guard_write(request, 'support_reply')
    form = ChatMessageForm(request.POST, request.FILES)
    if form.is_valid():
        existing = Message.objects.filter(ticket=ticket, author=request.user,
                                          request_key=form.cleaned_data['request_key']).first()
        if existing:
            return redirect(ticket_url(ticket.pk))
        try:
            if ticket.archived_at or ticket.status == Ticket.Status.SPAM:
                raise ValidationError(_('ERROR_SUPPORT_TICKET_CLOSED'))
            ids = stage_uploads(request.user, form.uploads())
            services.reply(ticket.pk, request.user, form.cleaned_data['body'], form.cleaned_data['request_key'], ids)
            return redirect(ticket_url(ticket.pk))
        except ValidationError as exc:
            form.add_error(None, exc)
    return render_ticket(request, ticket, form, status=400)


@support_access
@require_POST
@ratelimit(key=ip_key, rate='20/1m', block=True)
@ratelimit(key=user_key, rate='10/1m', block=True)
def ticket_close(request):
    ticket = owner_ticket(request)
    guard_write(request, 'support_reply')
    try:
        services.update_ticket(ticket.pk, request.user, status=Ticket.Status.RESOLVED)
    except ValidationError as exc:
        form = ChatMessageForm()
        form.add_error(None, exc)
        return render_ticket(request, ticket, form, status=400)
    return redirect(ticket_url(ticket.pk))


@support_access
@require_GET
def updates(request):
    ticket = owner_ticket(request)
    return JsonResponse({'revision': ticket.public_revision})


@support_access
@require_GET
def attachment_download(request, attachment_id):
    row = get_object_or_404(Attachment.objects.select_related('message__ticket'), pk=attachment_id,
                            message__ticket__owner=request.user, message__internal=False, file_id__isnull=False)
    response = redirect(download_url(row.file_id, request))
    response['Referrer-Policy'] = 'no-referrer'
    return response
