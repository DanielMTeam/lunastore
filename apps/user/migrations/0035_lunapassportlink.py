# Generated manually for LunaPassport OAuth link

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0033_alter_nospamrule_match_type_alter_nospamrule_pattern'),
    ]

    operations = [
        migrations.CreateModel(
            name='LunaPassportLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted', models.DateTimeField(db_index=True, editable=False, null=True)),
                ('deleted_by_cascade', models.BooleanField(default=False, editable=False)),
                ('sub', models.CharField(db_index=True, help_text='Stable identity from /oauth/userinfo (sub)', max_length=255, unique=True, verbose_name='Passport sub')),
                ('sign_in', models.EmailField(max_length=254, verbose_name='Passport sign_in')),
                ('passport_name', models.CharField(blank=True, default='', max_length=255, verbose_name='Passport display name')),
                ('linked_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='passport_link', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Привязка LunaPassport',
                'verbose_name_plural': 'Привязки LunaPassport',
            },
        ),
    ]
