from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0030_user_last_username_change"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoSpamRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Название правила")),
                ("is_enabled", models.BooleanField(db_index=True, default=True, verbose_name="Включено")),
                ("priority", models.PositiveIntegerField(db_index=True, default=100, help_text="Чем меньше число, тем выше приоритет.", verbose_name="Приоритет")),
                ("entrypoints", models.CharField(blank=True, default="", help_text="CSV: register,login,jwt_token,profile_update,profile_email,profile_username,dev_status", max_length=255, verbose_name="Точки входа")),
                ("action", models.CharField(choices=[("ban", "Бан"), ("delete", "Удаление"), ("log", "Только лог")], default="log", max_length=16, verbose_name="Действие")),
                ("match_type", models.CharField(choices=[("email_domain", "Домен email"), ("email_regex", "Email regex"), ("username_regex", "Username regex"), ("ip_cidr", "IP CIDR"), ("user_agent_regex", "User-Agent regex"), ("country_code", "Код страны"), ("invite_pattern", "Паттерн invite"), ("request_rate_signal", "Сигнал скорости запросов")], db_index=True, max_length=32, verbose_name="Тип фильтра")),
                ("pattern", models.CharField(blank=True, default="", max_length=255, verbose_name="Паттерн")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Доп. настройки")),
                ("reason_template", models.CharField(default="noSpam rule matched", max_length=255, verbose_name="Причина")),
                ("ban_by_ip", models.BooleanField(default=False, verbose_name="Банить по IP")),
                ("is_permanent", models.BooleanField(default=False, verbose_name="Перманентный бан")),
                ("ban_duration_minutes", models.PositiveIntegerField(default=60, verbose_name="Длительность бана (мин)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "noSpam правило",
                "verbose_name_plural": "noSpam правила",
                "ordering": ["priority", "-id"],
            },
        ),
        migrations.CreateModel(
            name="NoSpamEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entrypoint", models.CharField(max_length=32)),
                ("action", models.CharField(choices=[("ban", "Бан"), ("delete", "Удаление"), ("log", "Только лог")], default="log", max_length=16)),
                ("reason", models.CharField(max_length=255)),
                ("ip", models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ("matched_value", models.CharField(blank=True, default="", max_length=255)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("rule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="user.nospamrule")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="nospam_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "noSpam событие",
                "verbose_name_plural": "noSpam события",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="nospamrule",
            index=models.Index(fields=["is_enabled", "priority"], name="user_nospam_is_enabl_4ef28f_idx"),
        ),
        migrations.AddIndex(
            model_name="nospamrule",
            index=models.Index(fields=["match_type", "is_enabled"], name="user_nospam_match_t_7f3b10_idx"),
        ),
    ]
