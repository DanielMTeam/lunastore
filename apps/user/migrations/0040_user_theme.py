from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0039_alter_blacklistedusername_word_alter_user_email_and_more"),
    ]

    operations = [
        migrations.RunSQL("SET LOCAL lock_timeout = '2s'", reverse_sql=migrations.RunSQL.noop),
        migrations.AddField(
            model_name="user",
            name="theme",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=16,
                choices=[
                    ("classic_light", "THEME_CLASSIC_LIGHT"),
                    ("classic_dark", "THEME_CLASSIC_DARK"),
                    ("windows7", "THEME_WINDOWS7"),
                ],
            ),
        ),
        # Reverse operations run backwards: also protect the rollback DDL.
        migrations.RunSQL(migrations.RunSQL.noop, reverse_sql="SET LOCAL lock_timeout = '2s'"),
    ]
