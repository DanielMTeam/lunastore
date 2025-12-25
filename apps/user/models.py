from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid


class User(AbstractUser, models.Model):
    def unique_avatar_path(instance, filename):
        ext = filename.split('.')[-1]
        file_name = f"{uuid.uuid4().hex}.{ext}"
        return f'staticfiles/ugc/user_avatars/{file_name}'
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
    
    telegram = models.CharField(max_length=45, null=True)
    discord = models.CharField(max_length=32, null=True)
    website = models.URLField(max_length=45, null=True)
    avatar = models.ImageField(upload_to=unique_avatar_path, max_length=80, null=True)
    description = models.CharField(max_length=255, default='Пока что, описания тут нету')


class UserBan(models.Model):
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_logs')
    ip = models.GenericIPAddressField()
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Журнал активности"
        verbose_name_plural = "Журналы активности"


class DevRequestsModel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="developer_status_requests")
    github = models.URLField(max_length=128)
    mail = models.EmailField(max_length=128)
    about_you = models.TextField(max_length=1000)
    why_you_choose_us = models.TextField(max_length=250)
    
    class Meta:
        ordering = ['-id']
        verbose_name = "Заявка на статус разработчика"
        verbose_name_plural = "Заявки на статус разработчика"
