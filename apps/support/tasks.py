"""Durable outbox with short database leases; external calls never hold database locks."""
import html
import logging
import uuid
from datetime import timedelta

import requests
from constance import config
from django.conf import settings
from django.db import transaction
from django.tasks import task
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.core.notifications.services import NotificationService
from .models import Attachment, Delivery
from .storage import delete_staged

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


class DeliveryError(Exception):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


def _telegram(delivery):
    if not config.SUPPORT_TELEGRAM_ENABLED:
        return False

    def configured(value):
        value = str(value or '').strip()
        return '' if value in ('...', 'None') else value

    token = configured(settings.TELEGRAM_BOT_TOKEN)
    chat = configured(config.SUPPORT_TELEGRAM_CHAT_ID) or configured(settings.TELEGRAM_LOG_CHAT_ID)
    topic = configured(config.SUPPORT_TELEGRAM_TOPIC_ID) or configured(getattr(settings, 'TELEGRAM_LOG_TOPIC_ID', ''))
    if not token or not chat:
        raise DeliveryError('Telegram bot or chat is not configured')
    ticket = delivery.event.ticket
    labels = {'created': _('NOTIF_SUPPORT_NEW_TICKET'), 'customer_reply': _('EVENT_SUPPORT_CUSTOMER_REPLY'),
              'reopened': _('EVENT_SUPPORT_TICKET_REOPENED')}
    admin_path = reverse('admin:support_ticket_change', args=[ticket.pk], urlconf='lunastore.urls_private')
    admin_url = config.SUPPORT_ADMIN_BASE_URL.rstrip('/') + admin_path
    text = ('<b>{}</b> #{}\n{}\n{}: {}\n{}: {}\n<a href="{}">{}</a>').format(
        html.escape(str(labels.get(delivery.event.kind, _('SUPPORT_TICKET')))), ticket.pk,
        html.escape(ticket.subject), _('FORM_SUPPORT_AUTHOR'), html.escape(str(ticket.owner or _('SUPPORT_ACCOUNT_DELETED'))),
        _('FORM_SUPPORT_PRIORITY'), html.escape(str(ticket.get_priority_display())), html.escape(admin_url, quote=True),
        _('NOTIF_SUPPORT_OPEN_ADMIN'))
    payload = {'chat_id': chat, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if topic:
        try:
            payload['message_thread_id'] = int(topic)
        except (ValueError, TypeError):
            raise DeliveryError('Invalid Telegram topic id')
    response = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json=payload, timeout=(5, 10))
    if response.status_code == 429:
        try:
            delay = max(1, int(response.json().get('parameters', {}).get('retry_after', 60)))
        except (ValueError, TypeError):
            delay = 60
        raise DeliveryError('Telegram rate limit', retry_after=delay)
    if response.status_code != 200 or not response.json().get('ok'):
        # Never persist Telegram's URL, bot token, or response bodies in the admin error log.
        raise DeliveryError(f'Telegram HTTP {response.status_code}')
    return True


def _site(delivery):
    if not config.SUPPORT_SITE_NOTIFICATIONS_ENABLED:
        return False
    ticket = delivery.event.ticket
    if not ticket.owner_id:
        return False
    language = getattr(ticket.owner, 'language', settings.LANGUAGE_CODE)
    with translation.override(language):
        title = _('PAGE_SUPPORT_HEADING')
        content = (_('NOTIF_SUPPORT_REPLY_DESCRIPTION') if delivery.event.kind == 'staff_reply'
                   else _('NOTIF_SUPPORT_STATUS_DESCRIPTION'))
        success = NotificationService.send_notification(
            ticket.owner_id, str(title), str(content),
            meta={'type': 'info', 'action_url': f'/support_ticket.php?id={ticket.pk}',
                  'action_text': str(_('NOTIF_SUPPORT_OPEN_TICKET'))})
    if not success:
        raise DeliveryError('LunaSpire notification delivery failed')
    return True


@task()
def deliver_notification(delivery_id):
    now = timezone.now()
    lease = uuid.uuid4()
    with transaction.atomic():
        row = Delivery.objects.select_for_update().filter(pk=delivery_id).first()
        if not row or row.state not in (Delivery.State.PENDING, Delivery.State.SENDING) or row.available_at > now:
            return
        if row.attempts >= MAX_ATTEMPTS:
            row.state = Delivery.State.FAILED
            row.save(update_fields=['state'])
            return
        row.state = Delivery.State.SENDING
        row.attempts += 1
        row.lease_token = lease
        row.available_at = now + timedelta(minutes=2)
        row.save(update_fields=['state', 'attempts', 'lease_token', 'available_at'])
    row = Delivery.objects.select_related('event__ticket__owner').get(pk=delivery_id)
    try:
        sent = _telegram(row) if row.channel == 'telegram' else _site(row)
        Delivery.objects.filter(pk=row.pk, lease_token=lease).update(
            state=Delivery.State.SENT if sent else Delivery.State.SKIPPED, last_error='', lease_token=None)
    except Exception as exc:
        delay = max(min(30 * (2 ** (row.attempts - 1)), 3600), getattr(exc, 'retry_after', 0))
        available = timezone.now() + timedelta(seconds=delay)
        state = Delivery.State.FAILED if row.attempts >= MAX_ATTEMPTS else Delivery.State.PENDING
        # Requests exceptions can contain credential-bearing URLs; retain only our safe errors.
        error = str(exc)[:500] if isinstance(exc, DeliveryError) else type(exc).__name__
        updated = Delivery.objects.filter(pk=row.pk, lease_token=lease).update(
            state=state, available_at=available, last_error=error, lease_token=None)
        if updated and state == Delivery.State.PENDING:
            try:
                deliver_notification.using(run_after=available).enqueue(row.pk)
            except Exception:
                logger.warning('Support delivery %s awaits periodic retry', row.pk)


def sweep_deliveries():
    from .services import _wake
    due = Delivery.objects.filter(state__in=[Delivery.State.PENDING, Delivery.State.SENDING],
                                  available_at__lte=timezone.now()).order_by('available_at')
    for delivery_id in due.values_list('pk', flat=True)[:100]:
        _wake(delivery_id)


@task()
def cleanup_uploads():
    cutoff = timezone.now() - timedelta(days=1)
    for row in Attachment.objects.filter(message__isnull=True, created_at__lt=cutoff).order_by('pk')[:100]:
        try:
            delete_staged(row)
        except Exception as exc:
            logger.warning('Support upload cleanup failed for %s: %s', row.pk, type(exc).__name__)
