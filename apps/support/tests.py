import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import jwt
import requests
from PIL import Image
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import services, storage, tasks
from .forms import MessageForm, TicketForm
from .models import Attachment, Delivery, Message, ReadReceipt, Ticket, TicketEvent

TEST_SETTINGS = dict(
    MEILISEARCH_ENABLED=False, TELEGRAM_LOGGER_ENABLED=False, RATELIMIT_ENABLE=False,
    ALLOWED_HOSTS=['testserver', '127.0.0.1'],
    MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware'],
)


def ticket_data(**kwargs):
    return dict(subject='Ошибка загрузки', category='downloads', urgency='high',
                body='Загрузка прерывается на Windows XP.', request_key=uuid.uuid4(), **kwargs)


def support_config(**kwargs):
    defaults = dict(SUPPORT_ENABLED=True, SUPPORT_TELEGRAM_ENABLED=True,
                    SUPPORT_SITE_NOTIFICATIONS_ENABLED=True, SUPPORT_TELEGRAM_CHAT_ID='123',
                    SUPPORT_TELEGRAM_TOPIC_ID='', SUPPORT_ADMIN_BASE_URL='https://admin.example.com',
                    NOSPAM_FAIL_MODE='allow')
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class SupportFixtures:
    @classmethod
    def make_users(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username='support_owner', email='owner@example.com', password='example123')
        cls.other = User.objects.create_user(username='support_other', email='other@example.com', password='example123')
        cls.staff = User.objects.create_user(username='support_staff', email='staff@example.com',
                                             password='example123', is_staff=True)
        cls.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='support',
                                                                  codename__in=['view_ticket', 'process_ticket']))
        cls.staff2 = User.objects.create_user(username='support_staff2', email='staff2@example.com',
                                              password='example123', is_staff=True)
        cls.staff2.user_permissions.set(cls.staff.user_permissions.all())


@override_settings(**TEST_SETTINGS)
class SupportServiceTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def setUp(self):
        self.ticket = services.create_ticket(self.owner, ticket_data())

    def test_create_is_atomic_and_does_not_promote_user_urgency(self):
        self.assertEqual(self.ticket.priority, Ticket.Priority.NORMAL)
        self.assertEqual(self.ticket.urgency, Ticket.Urgency.HIGH)
        self.assertEqual(self.ticket.messages.count(), 1)
        self.assertEqual(Delivery.objects.get().channel, 'telegram')
        self.assertEqual(self.ticket.public_revision, 1)

    def test_create_and_reply_are_idempotent(self):
        data = ticket_data()
        first = services.create_ticket(self.owner, data)
        self.assertEqual(first.pk, services.create_ticket(self.owner, data).pk)
        key = uuid.uuid4()
        message = services.reply(first.pk, self.owner, 'Дополнение', key)
        self.assertEqual(message.pk, services.reply(first.pk, self.owner, 'Дополнение', key).pk)
        self.assertEqual(first.messages.count(), 2)

    def test_invalid_attachment_rolls_back_message_status_and_delivery(self):
        before = Delivery.objects.count()
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.owner, 'Пример', uuid.uuid4(), [999999])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.messages.count(), 1)
        self.assertEqual(self.ticket.status, 'new')
        self.assertEqual(Delivery.objects.count(), before)

    def test_status_lifecycle_and_internal_note(self):
        services.reply(self.ticket.pk, self.staff, 'Проверяем', uuid.uuid4(), staff=True)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'waiting')
        revision = self.ticket.public_revision
        services.reply(self.ticket.pk, self.staff, 'Служебная запись', uuid.uuid4(), staff=True, internal=True)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.public_revision, revision)
        self.assertEqual(self.ticket.status, 'waiting')
        services.reply(self.ticket.pk, self.owner, 'Проверил', uuid.uuid4())
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'in_progress')
        services.reply(self.ticket.pk, self.staff, 'Исправлено', uuid.uuid4(), staff=True, resolve=True)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'resolved')
        services.reply(self.ticket.pk, self.owner, 'Не помогло', uuid.uuid4())
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'in_progress')
        self.assertEqual(self.ticket.events.first().kind, 'reopened')

    def test_spam_and_archived_are_not_writable_by_owner(self):
        services.update_ticket(self.ticket.pk, self.staff, status='spam', priority=1, staff=True)
        with self.assertRaises(ValidationError):
            services.reply(self.ticket.pk, self.owner, 'Ответ', uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            services.update_ticket(self.ticket.pk, self.owner, status='resolved')
        Ticket.objects.filter(pk=self.ticket.pk).update(archived_at=timezone.now())
        with self.assertRaises(ValidationError):
            services.reply(self.ticket.pk, self.staff, 'Ответ', uuid.uuid4(), staff=True)

    def test_cannot_reply_or_manage_another_users_ticket(self):
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.other, 'Ответ', uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            services.update_ticket(self.ticket.pk, self.other, status='resolved')
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.owner, 'Скрытая запись', uuid.uuid4(), internal=True)

    def test_staff_flag_alone_does_not_grant_access(self):
        self.other.is_staff = True
        self.other.save()
        self.assertFalse(services.can_view_staff(self.other))
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.other, 'Ответ', uuid.uuid4(), staff=True)

    def test_read_cursors_are_per_staff_and_monotonic(self):
        first = self.ticket.messages.first()
        services.mark_read(self.ticket, self.staff, [first], staff=True)
        self.assertFalse(ReadReceipt.objects.filter(ticket=self.ticket, staff=self.staff2).exists())
        services.mark_read(self.ticket, self.staff, [], staff=True)
        self.assertEqual(ReadReceipt.objects.get(ticket=self.ticket, staff=self.staff).last_message_id, first.pk)
        answer = services.reply(self.ticket.pk, self.staff, 'Ответ', uuid.uuid4(), staff=True)
        services.mark_read(self.ticket, self.owner, [answer])
        services.mark_read(self.ticket, self.owner, [])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.owner_read_message_id, answer.pk)

    def test_priority_assignment_and_status_audit(self):
        services.update_ticket(self.ticket.pk, self.staff, status='in_progress', priority=3,
                               assignee_id=self.staff2.pk, staff=True)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, 3)
        self.assertEqual(self.ticket.assignee_id, self.staff2.pk)
        self.assertIn('status', self.ticket.events.first().changes)
        with self.assertRaises(ValidationError):
            services.update_ticket(self.ticket.pk, self.staff, status='new', priority=1,
                                   assignee_id=self.other.pk, staff=True)

    def test_delivery_is_created_only_on_commit_and_no_sync_fallback(self):
        with patch.object(type(tasks.deliver_notification), 'enqueue', side_effect=RuntimeError('Redis down')) as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                ticket = services.create_ticket(self.owner, ticket_data())
            self.assertTrue(enqueue.called)
            self.assertEqual(Delivery.objects.get(event__ticket=ticket).state, 'pending')

    def test_expired_or_foreign_upload_cannot_be_attached(self):
        row = Attachment.objects.create(uploader=self.other, file_id=100, original_name='log.txt', size=5,
                                        mimetype='text/plain')
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.owner, 'Ответ', uuid.uuid4(), [row.pk])
        row.uploader = self.owner
        row.created_at = timezone.now() - timedelta(days=2)
        row.save()
        with self.assertRaises(PermissionDenied):
            services.reply(self.ticket.pk, self.owner, 'Ответ', uuid.uuid4(), [row.pk])


@override_settings(**TEST_SETTINGS)
class SupportViewTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def setUp(self):
        self.ticket = services.create_ticket(self.owner, ticket_data())
        self.client.force_login(self.owner)
        for target in ('apps.support.views.config', 'apps.support.context_processors.config'):
            patcher = patch(target, support_config())
            patcher.start()
            self.addCleanup(patcher.stop)
        guard = patch('apps.support.views.guard_write')
        self.guard = guard.start()
        self.addCleanup(guard.stop)

    def test_create_and_follow_conversation_without_javascript(self):
        response = self.client.post(reverse('support:create'), ticket_data())
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertContains(response, 'Загрузка прерывается')
        self.assertContains(response, 'multipart/form-data')
        self.assertContains(response, 'name="file1"')
        self.assertNotContains(response, 'multiple=')

    def test_create_repeated_post_does_not_upload_twice(self):
        data = ticket_data()
        self.client.post(reverse('support:create'), data)
        with patch('apps.support.views.stage_uploads') as upload:
            self.assertEqual(self.client.post(reverse('support:create'), data).status_code, 302)
        upload.assert_not_called()

    def test_other_owner_cannot_read_poll_reply_close_or_download(self):
        message = self.ticket.messages.first()
        row = Attachment.objects.create(message=message, uploader=self.owner, file_id=10,
                                        original_name='log.txt', size=5, mimetype='text/plain')
        self.client.force_login(self.other)
        for name in ('detail', 'updates'):
            self.assertEqual(self.client.get(reverse('support:' + name), {'id': self.ticket.pk}).status_code, 404)
        for name in ('reply', 'close'):
            self.assertEqual(self.client.post(reverse('support:' + name) + f'?id={self.ticket.pk}', {}).status_code, 404)
        self.assertEqual(self.client.get(reverse('support:attachment', args=[row.pk])).status_code, 404)

    def test_note_body_files_and_revisions_are_hidden(self):
        before = self.client.get(reverse('support:updates'), {'id': self.ticket.pk}).json()
        note = services.reply(self.ticket.pk, self.staff, 'PRIVATE NOTE SECRET', uuid.uuid4(), staff=True, internal=True)
        row = Attachment.objects.create(message=note, uploader=self.staff, file_id=20,
                                        original_name='PRIVATE.log', size=4, mimetype='text/plain')
        response = self.client.get(reverse('support:detail'), {'id': self.ticket.pk})
        self.assertNotContains(response, 'PRIVATE')
        self.assertEqual(self.client.get(reverse('support:updates'), {'id': self.ticket.pk}).json(), before)
        self.assertEqual(self.client.get(reverse('support:attachment', args=[row.pk])).status_code, 404)

    def test_download_uses_short_lived_protocol_relative_url(self):
        row = Attachment.objects.create(message=self.ticket.messages.first(), uploader=self.owner, file_id=31,
                                        original_name='log.txt', size=4, mimetype='text/plain')
        response = self.client.get(reverse('support:attachment', args=[row.pk]))
        self.assertTrue(response.url.startswith('//'))
        from urllib.parse import urlsplit, parse_qs
        token = parse_qs(urlsplit(response.url).query)['token'][0]
        payload = jwt.decode(token, settings.LUNASPIRE_SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(payload['exp'] - payload['iat'], 60)
        self.assertEqual(payload['file_id'], 31)

    def test_upload_failure_preserves_text_and_does_not_publish(self):
        with patch('apps.support.views.stage_uploads', side_effect=ValidationError('Хранилище недоступно')):
            response = self.client.post(reverse('support:reply') + f'?id={self.ticket.pk}',
                                        {'body': 'Текст не потерян', 'request_key': uuid.uuid4()})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Текст не потерян', status_code=400)
        self.assertEqual(self.ticket.messages.count(), 1)

    def test_pagination_and_unread_counter(self):
        for i in range(24):
            services.reply(self.ticket.pk, self.staff, f'Ответ {i}', uuid.uuid4(), staff=True)
        response = self.client.get(reverse('support:list'))
        self.assertContains(response, 'Новый ответ')
        response = self.client.get(reverse('support:detail'), {'id': self.ticket.pk, 'page': 1})
        self.assertEqual(len(response.context['page_obj']), 20)
        self.ticket.refresh_from_db()
        self.assertLess(self.ticket.owner_read_message_id, self.ticket.last_staff_message_id)
        self.client.get(reverse('support:detail'), {'id': self.ticket.pk})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.owner_read_message_id, self.ticket.last_staff_message_id)

    def test_csrf_login_and_methods(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('support:create'), ticket_data()).status_code, 403)
        self.assertEqual(self.client.get(reverse('support:close'), {'id': self.ticket.pk}).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('support:list')).status_code, 302)

    @override_settings(RATELIMIT_ENABLE=True, RATELIMIT_BACKEND='memory')
    def test_rate_limit_counts_posts_and_does_not_count_form_views(self):
        from django_smart_ratelimit.backends import clear_backend_cache
        clear_backend_cache()
        self.addCleanup(clear_backend_cache)
        for _ in range(6):
            self.assertEqual(self.client.get(reverse('support:create')).status_code, 200)
        for _ in range(5):
            self.assertEqual(self.client.post(reverse('support:create'), ticket_data()).status_code, 302)
        self.assertEqual(self.client.post(reverse('support:create'), ticket_data()).status_code, 429)

    def test_fragment_refresh_contains_only_visible_thread_and_revision(self):
        services.reply(self.ticket.pk, self.staff, 'SECRET NOTE', uuid.uuid4(), staff=True, internal=True)
        response = self.client.get(reverse('support:detail'), {'id': self.ticket.pk, 'fragment': 1})
        self.assertContains(response, 'support-thread')
        self.assertContains(response, 'data-revision=')
        self.assertNotContains(response, '<form')
        self.assertNotContains(response, '<script')
        self.assertNotContains(response, 'SECRET NOTE')

    def test_problem_form_redirects_to_support(self):
        self.assertRedirects(self.client.get('/report_problem.php'), reverse('support:create'),
                             fetch_redirect_response=False)

    @override_settings(ROOT_URLCONF='lunastore.urls_private')
    def test_admin_thread_and_queue_render_and_process_reply(self):
        self.client.force_login(self.staff)
        url = reverse('admin:support_ticket_change', args=[self.ticket.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Внутренние заметки')
        self.assertEqual(self.client.get(reverse('admin:support_ticket_changelist')).status_code, 200)
        response = self.client.post(url, {'action': 'note', 'body': 'Внутреннее', 'request_key': uuid.uuid4()})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.ticket.messages.filter(internal=True).exists())
        response = self.client.post(url, {'action': 'resolve', 'body': 'Готово', 'request_key': uuid.uuid4()})
        self.assertEqual(response.status_code, 302)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'resolved')

    @override_settings(ROOT_URLCONF='lunastore.urls_private')
    def test_admin_staff_without_support_permissions_denied(self):
        self.other.is_staff = True
        self.other.save()
        self.client.force_login(self.other)
        for name in ('change', 'updates'):
            response = self.client.get(reverse('admin:support_ticket_' + name, args=[self.ticket.pk]))
            self.assertEqual(response.status_code, 403)

    def test_legacy_admin_is_readonly(self):
        from apps.marketplace.models import ProblemReportRequests
        model_admin = admin.site._registry[ProblemReportRequests]
        request = RequestFactory().get('/')
        request.user = self.staff
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(model_admin.actions_detail, [])


@override_settings(**TEST_SETTINGS)
class StorageTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def test_accepts_image_and_legacy_encoded_log(self):
        data = io.BytesIO()
        Image.new('RGB', (2, 2)).save(data, format='PNG')
        storage.validate_upload(SimpleUploadedFile('screen.png', data.getvalue()))
        storage.validate_upload(SimpleUploadedFile('report.log', 'Ошибка XP'.encode('cp1251')))

    def test_rejects_spoofed_oversized_or_active_files(self):
        for name, data in [('fake.png', b'MZ executable'), ('fake.jpg', b'not jpeg'),
                           ('script.txt', b'<html><script>alert(1)</script>'), ('bin.log', b'a\0b'),
                           ('big.txt', b'x' * (storage.MAX_SIZE + 1)), ('run.exe', b'MZ'), ('archive.zip', b'PK')]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                storage.validate_upload(SimpleUploadedFile(name, data))

    def test_form_rejects_four_files_and_duplicate_fields(self):
        from django.utils.datastructures import MultiValueDict
        data = {'body': 'Текст', 'request_key': uuid.uuid4()}
        files = MultiValueDict({'file1': [SimpleUploadedFile('a.log', b'log'), SimpleUploadedFile('b.log', b'log')]})
        self.assertFalse(MessageForm(data, files).is_valid())
        files = {f'file{i}': SimpleUploadedFile(f'{i}.txt', b'log') for i in range(1, 5)}
        self.assertFalse(MessageForm(data, files).is_valid())

    def test_partial_upload_is_tracked_and_no_message_is_published(self):
        response = Mock(status_code=202)

        def confirm(*args, **kwargs):
            claims = jwt.decode(kwargs['data']['token'], settings.LUNASPIRE_SECRET_KEY, algorithms=['HS256'])
            self.assertEqual(claims['mode'], 'private')
            self.assertEqual(Attachment.objects.filter(object_key=claims['guard']).count(), 1)
            response.json.return_value = {'confirm_token': storage.sign({
                'type': 'cdn-confirm', 'guard': claims['guard'], 'file_id': 99})}
            return response
        with patch('apps.support.storage.requests.post', side_effect=[requests.ConnectionError('offline')]):
            with self.assertRaises(ValidationError):
                storage.stage_uploads(self.owner, [SimpleUploadedFile('a.txt', b'log')])
        self.assertEqual(Attachment.objects.filter(message__isnull=True).count(), 1)

        def info(*args, **kwargs):
            row = Attachment.objects.order_by('-pk').first()
            return Mock(json=lambda: {'info': [{'id': 99, 'object_id': storage.object_name(row),
                                                'user_id': str(self.owner.pk), 'visibility': 'private',
                                                'size': 3, 'mimetype': 'text/plain; charset=utf-8'}]})

        with patch('apps.support.storage.requests.post', side_effect=confirm), \
                patch('apps.support.storage.requests.get', side_effect=info):
            ids = storage.stage_uploads(self.owner, [SimpleUploadedFile('a.txt', b'log')])
        self.assertEqual(Attachment.objects.get(pk=ids[0]).file_id, 99)
        self.assertFalse(Message.objects.exists())

    def test_cleanup_recovers_uncertain_upload_by_object_key(self):
        row = Attachment.objects.create(uploader=self.owner, original_name='log.txt', size=3, mimetype='text/plain',
                                        created_at=timezone.now() - timedelta(days=2))
        response = Mock()
        response.json.return_value = {'info': [{'id': 123}]}
        with patch('apps.support.storage.requests.get', return_value=response) as get, \
                patch('apps.support.storage.requests.delete', return_value=Mock(json=lambda: {'failed': []})) as delete:
            tasks.cleanup_uploads.call()
        self.assertFalse(Attachment.objects.filter(pk=row.pk).exists())
        query = jwt.decode(get.call_args.kwargs['params']['token'], settings.LUNASPIRE_SECRET_KEY, algorithms=['HS256'])
        self.assertIn(str(row.object_key), query['search_values'][0])
        self.assertTrue(delete.called)

    def test_cleanup_failure_keeps_record_for_next_sweep(self):
        row = Attachment.objects.create(uploader=self.owner, file_id=400, original_name='log.txt', size=3,
                                        mimetype='text/plain', created_at=timezone.now() - timedelta(days=2))
        with patch('apps.support.storage.requests.delete', side_effect=requests.ConnectionError()):
            tasks.cleanup_uploads.call()
        self.assertTrue(Attachment.objects.filter(pk=row.pk).exists())


@override_settings(**TEST_SETTINGS)
class DeliveryTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def setUp(self):
        self.ticket = services.create_ticket(self.owner, ticket_data())
        self.delivery = Delivery.objects.get()
        patcher = patch('apps.support.tasks.config', support_config())
        self.config = patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(TELEGRAM_BOT_TOKEN='test-token')
    def test_telegram_contains_metadata_only_and_escapes_title(self):
        self.ticket.subject = '<script>subject</script>'
        self.ticket.save()
        response = Mock(status_code=200)
        response.json.return_value = {'ok': True}
        with patch('apps.support.tasks.requests.post', return_value=response) as post:
            tasks.deliver_notification.call(self.delivery.pk)
            tasks.deliver_notification.call(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertEqual(post.call_count, 1, self.delivery.last_error)
        body = post.call_args.kwargs['json']['text']
        self.assertNotIn(self.ticket.messages.first().body, body)
        self.assertIn('&lt;script&gt;', body)
        self.assertIn('https://admin.example.com/', body)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, 'sent')

    def test_telegram_failure_reschedules_without_sleep(self):
        with patch('apps.support.tasks._telegram', side_effect=tasks.DeliveryError('Telegram rate limit', 120)), \
                patch.object(type(tasks.deliver_notification), 'using') as deferred:
            tasks.deliver_notification.call(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, 'pending')
        self.assertEqual(self.delivery.attempts, 1)
        self.assertGreater(self.delivery.available_at, timezone.now() + timedelta(seconds=110))
        self.assertTrue(deferred.called)

    def test_network_exception_does_not_leak_secrets(self):
        with patch('apps.support.tasks._telegram', side_effect=requests.ConnectionError('botSECRET/token')), \
                patch.object(type(tasks.deliver_notification), 'using'):
            tasks.deliver_notification.call(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertNotIn('SECRET', self.delivery.last_error)

    def test_final_failure_is_visible_and_can_be_retried(self):
        self.delivery.attempts = 4
        self.delivery.save()
        with patch('apps.support.tasks._telegram', side_effect=tasks.DeliveryError('offline')):
            tasks.deliver_notification.call(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, 'failed')
        request = RequestFactory().post('/')
        request.user = self.staff
        model_admin = admin.site._registry[Delivery]
        with patch.object(model_admin, 'message_user'):
            model_admin.retry_delivery(request, Delivery.objects.filter(pk=self.delivery.pk))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.state, 'pending')
        self.assertEqual(self.delivery.attempts, 0)

    def test_expired_lease_is_recovered_but_live_lease_is_not(self):
        Delivery.objects.filter(pk=self.delivery.pk).update(state='sending', available_at=timezone.now() + timedelta(minutes=1))
        with patch('apps.support.tasks._telegram', return_value=True) as send:
            tasks.deliver_notification.call(self.delivery.pk)
            send.assert_not_called()
            Delivery.objects.filter(pk=self.delivery.pk).update(available_at=timezone.now() - timedelta(seconds=1))
            tasks.deliver_notification.call(self.delivery.pk)
            self.assertEqual(send.call_count, 1)

    def test_sweep_recovers_unenqueued_rows(self):
        with patch('apps.support.services._wake') as wake:
            tasks.sweep_deliveries()
        wake.assert_called_once_with(self.delivery.pk)

    def test_site_content_never_contains_message_text(self):
        message = services.reply(self.ticket.pk, self.staff, '<img src=x onerror=alert(1)>SECRET', uuid.uuid4(), staff=True)
        delivery = Delivery.objects.get(channel='site')
        with patch('apps.support.tasks.NotificationService.send_notification', return_value=True) as send:
            tasks.deliver_notification.call(delivery.pk)
        args, kwargs = send.call_args
        self.assertNotIn('SECRET', str(args) + str(kwargs))
        self.assertEqual(kwargs['meta']['action_url'], f'/support_ticket.php?id={self.ticket.pk}')

    def test_lunaspire_failure_keeps_durable_pending_delivery(self):
        services.reply(self.ticket.pk, self.staff, 'Ответ', uuid.uuid4(), staff=True)
        delivery = Delivery.objects.get(channel='site')
        with patch('apps.support.tasks.NotificationService.send_notification', return_value=False), \
                patch.object(type(tasks.deliver_notification), 'using'):
            tasks.deliver_notification.call(delivery.pk)
        delivery.refresh_from_db()
        self.assertEqual(delivery.state, 'pending')


@override_settings(**TEST_SETTINGS)
class ConcurrentSupportTests(SupportFixtures, TransactionTestCase):
    def setUp(self):
        self.make_users()
        patcher = patch('apps.support.services._wake')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_simultaneous_duplicate_replies_create_one_message_and_event(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row locking requires PostgreSQL')
        ticket = services.create_ticket(self.owner, ticket_data())
        key = uuid.uuid4()

        def send():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.owner.pk)
                return services.reply(ticket.pk, user, 'Одновременный ответ', key).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: send(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Message.objects.filter(ticket=ticket).count(), 2)
        self.assertEqual(TicketEvent.objects.filter(ticket=ticket, kind='customer_reply').count(), 1)

    def test_simultaneous_ticket_creation_with_same_key_creates_one_ticket(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row locking requires PostgreSQL')
        data = ticket_data()

        def create():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.owner.pk)
                return services.create_ticket(user, data).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(Delivery.objects.count(), 1)


@override_settings(**TEST_SETTINGS)
class SupportMigrationTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def test_import_preserves_author_dates_status_archive_without_notifications(self):
        from importlib import import_module
        from django.db.migrations.loader import MigrationLoader
        apps = MigrationLoader(connection).project_state([('support', '0002_import_problem_reports')]).apps
        Report = apps.get_model('marketplace', 'ProblemReportRequests')
        date = timezone.now() - timedelta(days=10)
        ids = []
        for status in ('pending', 'resolved', 'dismissed'):
            row = Report.objects.create(user_id=self.owner.pk, description='Исторический текст', status=status)
            Report.objects.filter(pk=row.pk).update(created_at=date, deleted=date if status == 'dismissed' else None)
            ids.append(row.pk)
        migration = import_module('apps.support.migrations.0002_import_problem_reports')
        schema = SimpleNamespace(connection=connection)
        migration.import_reports(apps, schema)
        migration.import_reports(apps, schema)
        tickets = list(Ticket.objects.filter(legacy_report_id__in=ids).order_by('legacy_report_id'))
        self.assertEqual([row.status for row in tickets], ['new', 'in_progress', 'resolved'])
        self.assertEqual(len(tickets), 3)
        for row in tickets:
            self.assertEqual(row.owner_id, self.owner.pk)
            self.assertEqual(row.created_at, date)
            self.assertEqual(row.messages.filter(internal=False).count(), 1)
        self.assertEqual(tickets[-1].archived_at, date)
        self.assertTrue(tickets[-1].messages.filter(internal=True).exists())
        self.assertFalse(Delivery.objects.filter(event__ticket__in=tickets).exists())


@override_settings(**TEST_SETTINGS)
class SupportGuardTests(SupportFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_users()

    def request(self):
        request = RequestFactory().post('/support_reply.php', REMOTE_ADDR='192.0.2.1')
        request.user = self.owner
        return request

    def test_blocked_account_or_ip_cannot_write(self):
        from apps.user.models import UserBan
        from .views import guard_write
        with patch('apps.support.views.BlockBannedIP.get_banned_set', return_value={'192.0.2.1'}):
            with self.assertRaises(PermissionDenied):
                guard_write(self.request(), 'support_reply')
        UserBan.objects.create(user=self.owner, reason='Test ban', is_permanent=True)
        with patch('apps.support.views.BlockBannedIP.get_banned_set', return_value=set()):
            with self.assertRaises(PermissionDenied):
                guard_write(self.request(), 'support_reply')

    def test_nospam_fail_mode_and_block_decision(self):
        from .views import guard_write
        with patch('apps.support.views.config', support_config(NOSPAM_FAIL_MODE='deny')), \
                patch('apps.support.views.BlockBannedIP.get_banned_set', return_value=set()), \
                patch('apps.support.views.AntiSpamService.evaluate_and_apply', side_effect=RuntimeError()):
            with self.assertRaises(PermissionDenied):
                guard_write(self.request(), 'support_create')
        with patch('apps.support.views.BlockBannedIP.get_banned_set', return_value=set()), \
                patch('apps.support.views.AntiSpamService.evaluate_and_apply', return_value=SimpleNamespace(should_block=True)):
            with self.assertRaises(PermissionDenied):
                guard_write(self.request(), 'support_reply')

    def test_legacy_public_cdn_record_cannot_be_attached_or_deleted(self):
        response = Mock()

        def upload(*args, **kwargs):
            claims = jwt.decode(kwargs['data']['token'], settings.LUNASPIRE_SECRET_KEY, algorithms=['HS256'])
            response.json.return_value = {'confirm_token': storage.sign({
                'type': 'cdn-confirm', 'guard': claims['guard'], 'file_id': 999})}
            return response

        info = Mock(json=lambda: {'info': [{'id': 999, 'visibility': 'public', 'object_id': 'catalog',
                                            'user_id': '1', 'size': 3, 'mimetype': 'text/plain'}]})
        with patch('apps.support.storage.requests.post', side_effect=upload), \
                patch('apps.support.storage.requests.get', return_value=info):
            with self.assertRaises(ValidationError):
                storage.stage_uploads(self.owner, [SimpleUploadedFile('log.txt', b'log')])
        row = Attachment.objects.get()
        self.assertIsNone(row.file_id)
        no_match = Mock(json=lambda: {'info': []})
        with patch('apps.support.storage.requests.get', return_value=no_match), \
                patch('apps.support.storage.requests.delete') as delete:
            storage.delete_staged(row)
        delete.assert_not_called()


class SupportLocalizationTests(TestCase):
    def test_support_labels_and_notifications_are_translated_in_all_languages(self):
        from django.utils import translation
        from django.utils.translation import gettext
        expected = {'ru': 'Создать обращение', 'en': 'Create ticket', 'uk': 'Створити звернення',
                    'be': 'Стварыць зварот', 'kk': 'Өтініш жасау'}
        for language, label in expected.items():
            with self.subTest(language=language), translation.override(language):
                self.assertEqual(gettext('PAGE_SUPPORT_CREATE_TITLE'), label)
                if language != 'ru':
                    self.assertNotEqual(gettext('NOTIF_SUPPORT_REPLY_DESCRIPTION'),
                                        'Поддержка ответила на ваше обращение.')

    def test_support_translation_calls_use_named_message_ids(self):
        import ast
        import re
        from pathlib import Path

        root = Path(settings.BASE_DIR)
        for path in (root / 'apps/support').glob('*.py'):
            if path.name == 'tests.py':
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ('_', 'gettext') and node.args):
                    with self.subTest(path=path.name, line=node.lineno):
                        self.assertIsInstance(node.args[0], ast.Constant)
                        self.assertRegex(node.args[0].value, r'^[A-Z][A-Z0-9_]+$')
        for directory in ('templates/support', 'templates/admin/support'):
            for path in (root / directory).glob('*.html'):
                for match in re.finditer(r"{% trans ['\"](.*?)['\"]", path.read_text()):
                    with self.subTest(path=path.name, msgid=match[1]):
                        self.assertRegex(match[1], r'^[A-Z][A-Z0-9_]+$')

    def test_all_support_catalog_entries_use_named_ids_and_have_translations(self):
        import json
        import re
        from pathlib import Path
        from django.utils import translation
        from django.utils.translation import gettext

        root = Path(settings.BASE_DIR)
        reference_keys = None
        for language in ('ru', 'en', 'uk', 'be', 'kk'):
            text = (root / f'locale/{language}/LC_MESSAGES/django.po').read_text()
            support = text.split('# Support tickets\n', 1)[1]
            keys = [json.loads(match[1]) for match in re.finditer(r'^msgid (".*")$', support, re.M)]
            self.assertTrue(keys)
            self.assertEqual(len(keys), len(set(keys)))
            if reference_keys is None:
                reference_keys = set(keys)
            self.assertEqual(set(keys), reference_keys)
            with translation.override(language):
                for key in keys:
                    with self.subTest(language=language, msgid=key):
                        self.assertRegex(key, r'^[A-Z][A-Z0-9_]+$')
                        self.assertNotEqual(gettext(key), key)
