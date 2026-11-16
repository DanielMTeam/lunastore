from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0039_alter_blacklistedusername_word_alter_user_email_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            "SET LOCAL lock_timeout = '2s'",
            reverse_sql="SET LOCAL lock_timeout = '2s'",
        ),
        migrations.AddField(
            model_name='user',
            name='is_supporter',
            field=models.BooleanField(
                default=False,
                db_default=False,
                verbose_name='Поддерживает проект',
                help_text='Автоматически отображать бейдж supporter в профиле.',
            ),
        ),
    ]
