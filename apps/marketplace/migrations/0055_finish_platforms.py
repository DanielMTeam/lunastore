from importlib import import_module

from django.db import migrations


seed_platforms = import_module('apps.marketplace.migrations.0054_seed_platforms').seed_platforms


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('marketplace', '0054_seed_platforms')]
    operations = [
        # Run after all old application processes have stopped, to cover writes during rollout.
        migrations.RunPython(seed_platforms, migrations.RunPython.noop, atomic=False),
        *[
            migrations.RunSQL(
                sql='CREATE INDEX CONCURRENTLY IF NOT EXISTS marketplace_%s_platform_idx '
                    'ON marketplace_%s (platform_id)' % (table, table),
                reverse_sql='DROP INDEX CONCURRENTLY IF EXISTS marketplace_%s_platform_idx' % table,
            ) for table in ('distribution', 'distributioncreaterequests', 'distributioneditrequests')
        ],
        *[
            migrations.RunSQL(
                sql='ALTER TABLE marketplace_%s VALIDATE CONSTRAINT marketplace_%s_platform_fk' % (table, table),
                reverse_sql=migrations.RunSQL.noop,
            ) for table in ('distribution', 'distributioncreaterequests', 'distributioneditrequests')
        ],
    ]
