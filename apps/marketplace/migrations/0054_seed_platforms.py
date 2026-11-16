from django.db import migrations


def seed_platforms(apps, schema_editor):
    alias = schema_editor.connection.alias
    Platform = apps.get_model('marketplace', 'Platform')
    xp, _ = Platform.objects.using(alias).get_or_create(code='windows_xp', defaults={'name': 'Windows XP'})
    Platform.objects.using(alias).get_or_create(code='windows_7', defaults={'name': 'Windows 7'})
    for name in ('Application', 'AppCreateRequests', 'AppEditRequests'):
        model = apps.get_model('marketplace', name)
        through = model.platforms.through
        key = model._meta.model_name + '_id'
        last_pk = 0
        while True:
            ids = list(model._base_manager.using(alias).filter(
                pk__gt=last_pk, platforms__isnull=True,
            ).order_by('pk').values_list('pk', flat=True)[:1000])
            if not ids:
                break
            through.objects.using(alias).bulk_create(
                [through(**{key: pk, 'platform_id': xp.pk}) for pk in ids], ignore_conflicts=True,
            )
            last_pk = ids[-1]
    for name in ('Distribution', 'DistributionCreateRequests', 'DistributionEditRequests'):
        manager = apps.get_model('marketplace', name)._base_manager.using(alias)
        while True:
            ids = list(manager.filter(platform__isnull=True).order_by('pk').values_list('pk', flat=True)[:1000])
            if not ids:
                break
            manager.filter(pk__in=ids, platform__isnull=True).update(platform_id=xp.pk)


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('marketplace', '0053_platform_appcreaterequests_platforms_and_more')]
    operations = [migrations.RunPython(seed_platforms, migrations.RunPython.noop, atomic=False)]
