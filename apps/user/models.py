import datetime
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel


class User(AbstractUser, SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    def unique_avatar_path(instance, filename):
        ext = filename.split(".")[-1]
        file_name = f"{uuid.uuid4().hex}.{ext}"
        return f"ugc/user_avatars/{file_name}"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    telegram = models.CharField(max_length=45, null=True)
    discord = models.CharField(max_length=32, null=True)
    website = models.URLField(max_length=45, null=True)
    avatar = models.ImageField(upload_to=unique_avatar_path, max_length=80, null=True)
    description = models.CharField(
        max_length=255, default="Пока что, описания тут нету"
    )
    invited_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_users",
    )


class UserBan(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip = models.CharField(max_length=256, null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Блокировка"
        verbose_name_plural = "Блокировки"

    def __str__(self):
        return f"Ban for {self.user.username} - {self.reason}"


"""


this model stores EXCLUSIVELY temporary personal data,
which after a certain time (based on the RETENTION_ACTIVITY_LOG_DAYS variable), based on the GLDR policy


"""


class UserActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_logs"
    )
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invite_token"
    )
    code = models.CharField(max_length=12, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_expired(self):
        return timezone.now() > self.created_at + datetime.timedelta(hours=24)

    def refresh_code_if_expired(self):
        if not self.code or timezone.now() > self.created_at + datetime.timedelta(
            hours=24
        ):
            self.code = get_random_string(8)
            self.created_at = timezone.now()
            self.save()
        return self.code
