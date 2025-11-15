from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class User(AbstractUser, models.Model):
    telegram = models.CharField(max_length=45)
    discord = models.CharField(max_length=32)
    website = models.URLField(max_length=45)
    avatar = models.FileField(upload_to='staticfiles/ugc/user_avatars', max_length=80, null=True)

class UserBanForm(models.Model):
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
