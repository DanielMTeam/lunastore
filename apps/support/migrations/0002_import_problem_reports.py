import uuid

from django.db import migrations


def import_reports(apps, schema_editor):
    alias = schema_editor.connection.alias
    Report = apps.get_model('marketplace', 'ProblemReportRequests')
    Ticket = apps.get_model('support', 'Ticket')
    Message = apps.get_model('support', 'Message')
    Event = apps.get_model('support', 'TicketEvent')
    statuses = {'pending': 'new', 'resolved': 'in_progress', 'dismissed': 'resolved'}
    for report in Report._base_manager.using(alias).order_by('pk').iterator(chunk_size=500):
        ticket, created = Ticket.objects.using(alias).get_or_create(legacy_report_id=report.pk, defaults={
            'owner_id': report.user_id, 'subject': f'Сообщение о проблеме №{report.pk}',
            'category': 'other', 'status': statuses.get(report.status, 'new'),
            'created_at': report.created_at, 'updated_at': report.created_at, 'public_updated_at': report.created_at,
            'archived_at': report.deleted, 'request_key': uuid.uuid4(), 'public_revision': 1, 'staff_revision': 1,
        })
        if not created:
            continue
        message = Message.objects.using(alias).create(ticket_id=ticket.pk, author_id=report.user_id,
                                                      body=report.description, created_at=report.created_at,
                                                      request_key=uuid.uuid4())
        Ticket.objects.using(alias).filter(pk=ticket.pk).update(last_customer_message_id=message.pk)
        Event.objects.using(alias).create(ticket_id=ticket.pk, actor_id=None, kind='imported',
                                          changes={'legacy_status': report.status}, created_at=report.created_at)
        if report.status == 'dismissed':
            Message.objects.using(alias).create(ticket_id=ticket.pk, author_id=None, internal=True, from_staff=True,
                                                body='Старое обращение отклонено модератором.',
                                                created_at=report.created_at, request_key=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [
        ('support', '0001_initial'),
        ('marketplace', '0052_protect_existing_community_applications'),
    ]
    # Preserve imported conversations on rollback; the import is idempotent on reapplication.
    operations = [migrations.RunPython(import_reports, migrations.RunPython.noop)]
