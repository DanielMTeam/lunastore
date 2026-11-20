from django.db import migrations


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('marketplace', '0056_platform_not_null_checks')]
    operations = [
        migrations.RunSQL(
            'ALTER TABLE marketplace_%s VALIDATE CONSTRAINT marketplace_%s_platform_nn' % (table, table),
            migrations.RunSQL.noop,
        ) for table in ('distribution', 'distributioncreaterequests', 'distributioneditrequests')
    ]
