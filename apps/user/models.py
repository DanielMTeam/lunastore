from django.db import models
from django.contrib.auth.models import AbstractUser

class Role(models.IntegerChoices):
    USER = 1, "User"
    ADMIN = 2, "Admin"
    ROOT = 3, "Root"

class User(AbstractUser, models.Model):
    telegram = models.CharField(max_length=45)
    discord = models.CharField(max_length=32)
    website = models.URLField(max_length=45)
    avatar = models.FileField(upload_to='staticfiles/ugc/user_avatars', max_length=80, null=True)
    role = models.IntegerField(choices=Role.choices, default=Role.USER)

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
