from django.db import migrations


TABLES = ('distribution', 'distributioncreaterequests', 'distributioneditrequests')


class Migration(migrations.Migration):
    dependencies = [('marketplace', '0055_finish_platforms')]
    operations = [
        migrations.RunSQL("SET LOCAL lock_timeout = '2s'", migrations.RunSQL.noop),
        *[
            migrations.RunSQL(
                'ALTER TABLE marketplace_%s ADD CONSTRAINT marketplace_%s_platform_nn '
                'CHECK (platform_id IS NOT NULL) NOT VALID' % (table, table),
                'ALTER TABLE marketplace_%s DROP CONSTRAINT marketplace_%s_platform_nn' % (table, table),
            ) for table in TABLES
        ],
        migrations.RunSQL(migrations.RunSQL.noop, "SET LOCAL lock_timeout = '2s'"),
    ]
