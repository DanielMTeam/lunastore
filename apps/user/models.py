from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser, models.Model):
    telegram = models.CharField(max_length=45)
    discord = models.CharField(max_length=32)
    website = models.URLField(max_length=45)
    avatar = models.FileField(upload_to='staticfiles/ugc/user_avatars', max_length=80, null=True)

class UserBan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    #ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Блокировка"
        verbose_name_plural = "Блокировки"

    def __str__(self):
        return f"Ban for {self.user.username} - {self.reason}"
