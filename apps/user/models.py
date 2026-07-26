import datetime
import hashlib
import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel
from .validators import validate_email_mx


class User(AbstractUser, SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    email = models.EmailField(
        unique=True,
        error_messages={
            "unique": _("ERROR_EMAIL_ALREADY_IN_USE"),
        },
        validators=[validate_email_mx],
    )
    telegram = models.CharField(max_length=45, null=True, blank=True)
    discord = models.CharField(max_length=32, null=True, blank=True)
    openvk = models.CharField(max_length=45, null=True, blank=True)
    badges = models.CharField(max_length=255, null=True, blank=True)
    website = models.URLField(max_length=45, null=True, blank=True)
    description = models.CharField(
        max_length=255,
        default="Пользователь не оставил описание, но надеемся, что он крут",
        blank=True)
    profile_splash = models.CharField(max_length=255, null=True, blank=True)
    invited_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_users",
    )
    avatar_id = models.PositiveIntegerField(null=True, blank=True)
    avatar_path = models.CharField(max_length=255, null=True, blank=True)
    totp_secret = models.CharField(max_length=32, null=True, blank=True)
    totp_enabled = models.BooleanField(default=False)
    last_username_change = models.DateTimeField(null=True, blank=True)

    @property
    def avatar_url(self) -> str:
        if self.avatar_path:
            from apps.core.local import get_geo_spire_url
            base_url = get_geo_spire_url(
                getattr(
                    settings,
                    "LUNASPIRE_URL",
                    "")).rstrip("/")
            protocol_relative_url = base_url.replace(
                "https:", "").replace("http:", "")

            path = self.avatar_path.lstrip("/")
            return f"{protocol_relative_url}/{path}"
        return "/staticfiles/img/noavatar_64.jpg"

    @property
    def badge_list(self):
        if not self.badges:
            return []
        return [tag.strip() for tag in self.badges.split(";")]


class UserBan(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip = models.GenericIPAddressField(
        "IP адрес", null=True, blank=True, db_index=True)
    reason = models.CharField("Причина", max_length=255)

    ban_by_ip = models.BooleanField("Блокировка по IP", default=False)
    is_permanent = models.BooleanField("Постоянная блокировка", default=False)
    expires_at = models.DateTimeField("Дата истечения", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Блокировка"
        verbose_name_plural = "Блокировки"

    def __str__(self):
        status = "Permanent" if self.is_permanent else f"Temp until {
            self.expires_at}"
        return f"Ban for {self.user.username} ({status}) - {self.reason}"


"""


this model stores EXCLUSIVELY temporary personal data,
which after a certain time (based on the RETENTION_ACTIVITY_LOG_DAYS variable), based on the GDPR policy


"""


class UserActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_logs")
    ip = models.GenericIPAddressField()
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Журнал активности"
        verbose_name_plural = "Журналы активности"


class DevRequestsModel(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="developer_status_requests",
    )
    github = models.URLField(max_length=128)
    mail = models.EmailField(max_length=128)
    about_you = models.TextField(max_length=1000)
    why_you_choose_us = models.TextField(max_length=250)

    class Meta:
        ordering = ["-id"]
        verbose_name = "Заявка на статус разработчика"
        verbose_name_plural = "Заявки на статус разработчика"


class BlacklistedUsername(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    word = models.CharField(
        max_length=50, unique=True, verbose_name="Запрещённый юзернейм"
    )
    is_regex = models.BooleanField(
        default=False, verbose_name="Это регулярное выражение? (regex type)"
    )

    def __str__(self):
        return self.word

    class Meta:
        verbose_name = "Бан-ворд (юзернейм)"
        verbose_name_plural = "Бан-ворды (юзернеймы)"


class InviteToken(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invite_token")
    code = models.CharField(max_length=12, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + datetime.timedelta(hours=24)

    def refresh_code_if_expired(self):
        if not self.code or timezone.now() > self.created_at + \
                datetime.timedelta(hours=24):
            self.code = get_random_string(8)
            self.created_at = timezone.now()
            self.save()
        return self.code

    class Meta:
        verbose_name = "Токен приглашения"
        verbose_name_plural = "Токены приглашения"


class UserSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_sessions")
    session_key = models.CharField(max_length=40, unique=True)
    ip = models.GenericIPAddressField("IP адрес", null=True, blank=True)
    user_agent = models.CharField(
        "Браузер",
        max_length=255,
        null=True,
        blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity"]
        verbose_name = "Активная сессия"
        verbose_name_plural = "Активные сессии"

    def __str__(self):
        return f"Сессия {self.user.username} ({self.ip})"


class NoSpamRule(models.Model):
    class RuleAction(models.TextChoices):
        BAN = "ban", "Бан"
        DELETE = "delete", "Удаление"
        LOG = "log", "Только лог"

    class MatchType(models.TextChoices):
        EMAIL_DOMAIN = "email_domain", "Домен email"
        EMAIL_REGEX = "email_regex", "Email regex"
        USERNAME_REGEX = "username_regex", "Username regex"
        IP_CIDR = "ip_cidr", "IP CIDR"
        USER_AGENT_REGEX = "user_agent_regex", "User-Agent regex"
        COUNTRY_CODE = "country_code", "Код страны"
        INVITE_PATTERN = "invite_pattern", "Паттерн invite"
        REQUEST_RATE_SIGNAL = "request_rate_signal", "Сигнал скорости запросов"
        USER_ID_RANGE = "user_id_range", "Диапазон ID пользователя"

    name = models.CharField("Название правила", max_length=120, unique=True)
    is_enabled = models.BooleanField("Включено", default=True, db_index=True)
    priority = models.PositiveIntegerField(
        "Приоритет",
        default=100,
        db_index=True,
        help_text="Чем меньше число, тем выше приоритет.",
    )
    entrypoints = models.CharField(
        "Точки входа",
        max_length=255,
        blank=True,
        default="",
        help_text="CSV: register,login,jwt_token,profile_update,profile_email,profile_username,dev_status",
    )
    action = models.CharField(
        "Действие",
        max_length=16,
        choices=RuleAction.choices,
        default=RuleAction.LOG,
    )
    match_type = models.CharField(
        "Тип фильтра",
        max_length=32,
        choices=MatchType.choices,
        db_index=True,
    )
    pattern = models.CharField(
        "Паттерн",
        max_length=255,
        blank=True,
        default="",
        help_text="Для диапазона ID: min:max, например 100:500",
    )
    payload = models.JSONField("Доп. настройки", default=dict, blank=True)
    reason_template = models.CharField(
        "Причина",
        max_length=255,
        default="noSpam rule matched",
    )
    ban_by_ip = models.BooleanField("Банить по IP", default=False)
    is_permanent = models.BooleanField("Перманентный бан", default=False)
    ban_duration_minutes = models.PositiveIntegerField(
        "Длительность бана (мин)",
        default=60,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "-id"]
        verbose_name = "noSpam правило"
        verbose_name_plural = "noSpam правила"
        indexes = [
            models.Index(fields=["is_enabled", "priority"]),
            models.Index(fields=["match_type", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.match_type} -> {self.action})"

    def get_entrypoints(self) -> set[str]:
        if not self.entrypoints.strip():
            return set()
        return {item.strip() for item in self.entrypoints.split(",") if item.strip()}

    def applies_to_entrypoint(self, entrypoint: str) -> bool:
        configured = self.get_entrypoints()
        if not configured:
            return True
        return entrypoint in configured


class NoSpamEvent(models.Model):
    rule = models.ForeignKey(
        NoSpamRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nospam_events",
    )
    entrypoint = models.CharField(max_length=32)
    action = models.CharField(
        max_length=16,
        choices=NoSpamRule.RuleAction.choices,
        default=NoSpamRule.RuleAction.LOG,
    )
    reason = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    matched_value = models.CharField(max_length=255, blank=True, default="")
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "noSpam событие"
        verbose_name_plural = "noSpam события"

    def __str__(self) -> str:
        return f"{self.entrypoint}: {self.action} ({self.reason})"
