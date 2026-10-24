import logging
from functools import partial
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Attachment, Delivery, Message, ReadReceipt, Ticket, TicketEvent

logger = logging.getLogger(__name__)


def can_view_staff(user):
    return user.is_active and user.is_staff and user.has_perm('support.view_ticket')


def can_process(user):
    return can_view_staff(user) and user.has_perm('support.process_ticket')


def assert_owner(ticket, user):
    if not user.is_authenticated or ticket.owner_id != user.pk:
        raise PermissionDenied


def _writable(ticket):
    if ticket.archived_at:
        raise ValidationError(_('ERROR_SUPPORT_ARCHIVED_READ_ONLY'))


def _wake(delivery_id):
    from .tasks import deliver_notification
    try:
        deliver_notification.enqueue(delivery_id)
    except Exception:
        # The periodic DB sweep will recover this. Never call external services from the request.
        logger.warning('Support notification enqueue failed; delivery %s remains pending', delivery_id)


def event(ticket, actor, kind, changes=None, channel=None):
    row = TicketEvent.objects.create(ticket=ticket, actor=actor, kind=kind, changes=changes or {})
    if channel and (channel != 'site' or ticket.owner_id):
        delivery = Delivery.objects.create(event=row, channel=channel)
        transaction.on_commit(partial(_wake, delivery.pk))
    return row


def _attach(message, user, attachment_ids):
    if len(attachment_ids) > 3 or len(set(attachment_ids)) != len(attachment_ids):
        raise ValidationError(_('ERROR_SUPPORT_ATTACHMENT_COUNT'))
    rows = list(Attachment.objects.select_for_update().filter(pk__in=attachment_ids))
    if (len(rows) != len(attachment_ids)
            or any(row.uploader_id != user.pk or row.message_id or not row.file_id
                   or row.created_at < timezone.now() - timedelta(days=1) for row in rows)):
        raise PermissionDenied
    Attachment.objects.filter(pk__in=attachment_ids).update(message=message)


def _message(ticket, user, body, request_key, attachment_ids, internal=False, staff=False):
    body = body.strip()
    if not body or len(body) > 10000:
        raise ValidationError(_('ERROR_SUPPORT_MESSAGE_LENGTH'))
    message = Message.objects.create(ticket=ticket, author=user, body=body, request_key=request_key,
                                     internal=internal, from_staff=staff)
    _attach(message, user, attachment_ids)
    ticket.updated_at = timezone.now()
    ticket.staff_revision += 1
    if not internal:
        ticket.public_revision += 1
        ticket.public_updated_at = ticket.updated_at
        if staff:
            ticket.last_staff_message_id = message.pk
        else:
            ticket.last_customer_message_id = message.pk
    return message


@transaction.atomic
def create_ticket(user, data, attachment_ids=()):
    # Lock the owner to serialize repeated create requests before the unique key is inserted.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    existing = Ticket.objects.filter(request_key=data['request_key']).first()
    if existing:
        assert_owner(existing, user)
        return existing
    ticket = Ticket(owner=user, subject=data['subject'].strip(), category=data['category'], urgency=data['urgency'],
                    request_key=data['request_key'])
    ticket.full_clean()
    ticket.save()
    _message(ticket, user, data['body'], data['request_key'], attachment_ids)
    ticket.save()
    event(ticket, user, 'created', channel='telegram')
    return ticket


@transaction.atomic
def reply(ticket_id, user, body, request_key, attachment_ids=(), staff=False, internal=False, resolve=False):
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    if staff:
        if not can_process(user):
            raise PermissionDenied
    else:
        assert_owner(ticket, user)
        if internal or resolve:
            raise PermissionDenied
    _writable(ticket)
    existing = Message.objects.filter(request_key=request_key).first()
    if existing:
        if existing.author_id != user.pk or existing.ticket_id != ticket.pk:
            raise PermissionDenied
        return existing
    if not staff and ticket.status == Ticket.Status.SPAM:
        raise ValidationError(_('ERROR_SUPPORT_TICKET_CLOSED'))
    old_status = ticket.status
    message = _message(ticket, user, body, request_key, attachment_ids, internal=internal, staff=staff)
    if not internal:
        ticket.status = (Ticket.Status.RESOLVED if resolve else Ticket.Status.WAITING) if staff else Ticket.Status.IN_PROGRESS
    ticket.save()
    kind = 'note' if internal else ('staff_reply' if staff else 'customer_reply')
    if not staff and old_status == Ticket.Status.RESOLVED:
        kind = 'reopened'
    changes = {'message_id': message.pk}
    if ticket.status != old_status:
        changes['status'] = [old_status, ticket.status]
    event(ticket, user, kind, changes, channel=None if internal else ('site' if staff else 'telegram'))
    return message


@transaction.atomic
def update_ticket(ticket_id, actor, *, status=None, priority=None, assignee_id=None, staff=False):
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    _writable(ticket)
    if staff:
        if not can_process(actor):
            raise PermissionDenied
        if status not in Ticket.Status.values or priority not in Ticket.Priority.values:
            raise ValidationError(_('ERROR_SUPPORT_INVALID_STATUS_OR_PRIORITY'))
        if assignee_id:
            from .forms import eligible_staff
            if not eligible_staff().filter(pk=assignee_id).exists():
                raise ValidationError(_('ERROR_SUPPORT_ASSIGNEE_UNAVAILABLE'))
        values = {'status': status, 'priority': priority, 'assignee_id': assignee_id}
    else:
        assert_owner(ticket, actor)
        if status != Ticket.Status.RESOLVED or ticket.status == Ticket.Status.SPAM:
            raise PermissionDenied
        values = {'status': status}
    changes = {key: [getattr(ticket, key), value] for key, value in values.items() if getattr(ticket, key) != value}
    if changes:
        for key, value in values.items():
            setattr(ticket, key, value)
        ticket.staff_revision += 1
        ticket.updated_at = timezone.now()
        if 'status' in changes:
            ticket.public_revision += 1
            ticket.public_updated_at = ticket.updated_at
        ticket.save()
        event(ticket, actor, 'updated', changes, channel='site' if staff and 'status' in changes else None)
    return ticket


def mark_read(ticket, user, messages, staff=False):
    if staff:
        last_id = max((m.pk for m in messages if not m.internal and not m.from_staff), default=0)
        receipt, _created = ReadReceipt.objects.get_or_create(ticket=ticket, staff=user)
        ReadReceipt.objects.filter(pk=receipt.pk, last_message_id__lt=last_id).update(last_message_id=last_id)
    else:
        last_id = max((m.pk for m in messages if not m.internal and m.from_staff), default=0)
        Ticket.objects.filter(pk=ticket.pk, owner_read_message_id__lt=last_id).update(owner_read_message_id=last_id)
