import django.db.models.deletion
from django.db import migrations, models


TABLES = ('distribution', 'distributioncreaterequests', 'distributioneditrequests')


class Migration(migrations.Migration):
    dependencies = [('marketplace', '0057_validate_platform_checks')]
    operations = [
        migrations.RunSQL("SET LOCAL lock_timeout = '2s'", migrations.RunSQL.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE marketplace_%s ALTER COLUMN platform_id SET NOT NULL; '
                    'ALTER TABLE marketplace_%s DROP CONSTRAINT marketplace_%s_platform_nn' % (table, table, table),
                    # A rollback needs a separately staged, validated check before reapplying this migration.
                    reverse_sql=None,
                ) for table in TABLES
            ],
            state_operations=[
                migrations.AlterField(
                    model_name=table, name='platform',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            to='marketplace.platform', verbose_name='Платформа'),
                ) for table in TABLES
            ],
        ),
        migrations.RunSQL(migrations.RunSQL.noop, "SET LOCAL lock_timeout = '2s'"),
    ]
