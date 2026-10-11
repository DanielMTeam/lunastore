from django.conf import settings
from django.db import migrations, models

import apps.marketplace.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("marketplace", "0050_appcreaterequests_allow_community_distributions_and_more"),
    ]

    operations = [
        migrations.RunSQL("SET LOCAL lock_timeout = '2s'", reverse_sql=migrations.RunSQL.noop),
        migrations.AddField(
            model_name="application",
            name="community_protected",
            field=models.BooleanField(default=False, db_default=False, editable=False),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE marketplace_application ALTER COLUMN user_id DROP NOT NULL",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="application",
                    name="user",
                    field=models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=apps.marketplace.deletion.preserve_community_applications,
                        related_name="applications",
                        verbose_name="Автор",
                        null=True,
                        blank=True,
                    ),
                ),
            ],
        ),
        # Reverse operations run in reverse order: set the timeout before dropping the column.
        migrations.RunSQL(migrations.RunSQL.noop, reverse_sql="SET LOCAL lock_timeout = '2s'"),
    ]
