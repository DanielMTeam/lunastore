import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Ticket(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', _('MODEL_SUPPORT_STATUS_NEW')
        IN_PROGRESS = 'in_progress', _('MODEL_SUPPORT_STATUS_IN_PROGRESS')
        WAITING = 'waiting', _('MODEL_SUPPORT_STATUS_WAITING')
        RESOLVED = 'resolved', _('MODEL_SUPPORT_STATUS_RESOLVED')
        SPAM = 'spam', _('MODEL_SUPPORT_STATUS_SPAM')

    class Category(models.TextChoices):
        WEBSITE = 'website', _('SUPPORT_SITE')
        ACCOUNT = 'account', _('MODEL_SUPPORT_CATEGORY_ACCOUNT')
        DOWNLOADS = 'downloads', _('MODEL_SUPPORT_CATEGORY_DOWNLOADS')
        OTHER = 'other', _('MODEL_SUPPORT_CATEGORY_OTHER')

    class Urgency(models.TextChoices):
        NORMAL = 'normal', _('MODEL_SUPPORT_URGENCY_NORMAL')
        HIGH = 'high', _('MODEL_SUPPORT_URGENCY_HIGH')

    class Priority(models.IntegerChoices):
        LOW = 0, _('MODEL_SUPPORT_PRIORITY_LOW')
        NORMAL = 1, _('MODEL_SUPPORT_PRIORITY_NORMAL')
        HIGH = 2, _('MODEL_SUPPORT_PRIORITY_HIGH')
        CRITICAL = 3, _('MODEL_SUPPORT_PRIORITY_CRITICAL')

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='support_tickets', verbose_name=_('FORM_SUPPORT_AUTHOR'))
    subject = models.CharField(_('FORM_SUPPORT_SUBJECT'), max_length=200)
    category = models.CharField(_('FORM_SUPPORT_CATEGORY'), max_length=20, choices=Category, default=Category.OTHER)
    urgency = models.CharField(_('FORM_SUPPORT_URGENCY'), max_length=10, choices=Urgency, default=Urgency.NORMAL)
    priority = models.PositiveSmallIntegerField(_('FORM_SUPPORT_PRIORITY'), choices=Priority, default=Priority.NORMAL)
    status = models.CharField(_('FORM_SUPPORT_STATUS'), max_length=20, choices=Status, default=Status.NEW)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='assigned_support_tickets', verbose_name=_('FORM_SUPPORT_ASSIGNEE'))
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)
    public_updated_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)
    public_revision = models.PositiveBigIntegerField(default=0)
    staff_revision = models.PositiveBigIntegerField(default=0)
    last_customer_message_id = models.PositiveBigIntegerField(default=0)
    last_staff_message_id = models.PositiveBigIntegerField(default=0)
    owner_read_message_id = models.PositiveBigIntegerField(default=0)
    request_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    legacy_report_id = models.PositiveBigIntegerField(null=True, unique=True, editable=False)

    class Meta:
        verbose_name = _('MODEL_SUPPORT_TICKET')
        verbose_name_plural = _('MODEL_SUPPORT_TICKETS')
        ordering = ['-priority', 'updated_at', 'pk']
        permissions = [('process_ticket', 'Can reply to and manage support tickets')]
        indexes = [
            models.Index(fields=['status', '-priority', 'updated_at']),
            models.Index(fields=['owner', '-public_updated_at']),
            models.Index(fields=['assignee', 'status']),
        ]

    def __str__(self):
        return f'#{self.pk} — {self.subject}'


class Message(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    body = models.TextField(max_length=10000)
    internal = models.BooleanField(default=False)
    from_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    request_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['pk']
        indexes = [models.Index(fields=['ticket', 'internal', 'id'])]


class Attachment(models.Model):
    # A row exists BEFORE contacting storage, so interrupted uploads can be recovered by object_key.
    message = models.ForeignKey(Message, null=True, on_delete=models.CASCADE, related_name='attachments')
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    object_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    file_id = models.PositiveBigIntegerField(null=True, unique=True)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    mimetype = models.CharField(max_length=100)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=['message', 'created_at'])]


class TicketEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=30)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def label(self):
        return {
            'created': _('EVENT_SUPPORT_TICKET_CREATED'), 'customer_reply': _('EVENT_SUPPORT_CUSTOMER_REPLY'),
            'staff_reply': _('EVENT_SUPPORT_STAFF_REPLY'), 'note': _('SUPPORT_INTERNAL_NOTE'),
            'reopened': _('EVENT_SUPPORT_TICKET_REOPENED'), 'updated': _('EVENT_SUPPORT_SETTINGS_UPDATED'),
            'imported': _('EVENT_SUPPORT_LEGACY_IMPORTED'),
        }.get(self.kind, _('EVENT_SUPPORT_GENERIC'))

    @property
    def summary(self):
        parts = []
        for key, values in self.changes.items():
            if key == 'status':
                parts.append(str(_('FORM_SUPPORT_STATUS')) + ': ' + str(dict(Ticket.Status.choices).get(values[1], values[1])))
            elif key == 'priority':
                parts.append(str(_('FORM_SUPPORT_PRIORITY')) + ': ' + str(dict(Ticket.Priority.choices).get(values[1], values[1])))
            elif key == 'assignee_id':
                parts.append(str(_('EVENT_SUPPORT_ASSIGNEE_CHANGED')))
        return '; '.join(parts)

    class Meta:
        ordering = ['-pk']


class ReadReceipt(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_message_id = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ticket', 'staff'], name='support_unique_reader')]


class Delivery(models.Model):
    class State(models.TextChoices):
        PENDING = 'pending', _('MODEL_SUPPORT_DELIVERY_PENDING')
        SENDING = 'sending', _('MODEL_SUPPORT_DELIVERY_SENDING')
        SENT = 'sent', _('MODEL_SUPPORT_DELIVERY_SENT')
        FAILED = 'failed', _('MODEL_SUPPORT_DELIVERY_FAILED')
        SKIPPED = 'skipped', _('MODEL_SUPPORT_DELIVERY_SKIPPED')

    event = models.ForeignKey(TicketEvent, on_delete=models.CASCADE)
    channel = models.CharField(max_length=10, choices=[('telegram', 'Telegram'), ('site', _('SUPPORT_SITE'))])
    state = models.CharField(_('MODEL_SUPPORT_DELIVERY_STATE'), max_length=10, choices=State, default=State.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, editable=False)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _('MODEL_SUPPORT_DELIVERY')
        verbose_name_plural = _('MODEL_SUPPORT_DELIVERIES')
        constraints = [models.UniqueConstraint(fields=['event', 'channel'], name='support_unique_delivery')]
        indexes = [models.Index(fields=['state', 'available_at'])]
