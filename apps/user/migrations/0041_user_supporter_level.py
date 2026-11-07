from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('user', '0040_user_is_supporter')]

    operations = [
        migrations.RunSQL("SET LOCAL lock_timeout = '2s'", reverse_sql="SET LOCAL lock_timeout = '2s'"),
        migrations.AddField(
            model_name='user',
            name='supporter_level',
            field=models.PositiveSmallIntegerField(
                choices=[(1, '1 — синяя звезда'), (2, '2 — жёлтая звезда'), (3, '3 — красная звезда')],
                default=1,
                db_default=1,
                verbose_name='Уровень поддержки',
            ),
        ),
    ]
