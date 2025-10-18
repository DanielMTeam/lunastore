from django.db import models
from django.conf import settings
import os 

class Category(models.Model):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=140)
    shortcode = models.CharField(max_length=50,default='index.php')

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Category {self.name}>"


class Application(models.Model):
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=210)
    icon = models.FileField(upload_to='staticfiles/ugc/app_icons',max_length=140, null=True)
    screenshots = models.FileField(upload_to='staticfiles/ugc/screenshots', max_length=525, null=True)
    #screenshots = models.JSONField(default=list)

    class Meta:
        ordering = ["title"]
        verbose_name = "Приложение"
        verbose_name_plural = "Приложения"

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<Application {self.title}>"


class Distribution(models.Model):
    app = models.ForeignKey(Application, on_delete=models.PROTECT)
    version = models.CharField(max_length=20)
    file = models.FileField(upload_to='staticfiles/ugc/distributions',max_length=80, null=True)
    url = models.URLField(max_length=140, null=True)
    changelog = models.CharField(max_length=210)
    published = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["app", "published"]
        verbose_name = "Дистрибуция"
        verbose_name_plural = "Дистрибуции"

    def __str__(self):
        return f"{self.app} {self.version}"

    def __repr__(self):
        return f"<Distribution {self.app} {self.version}>"


# TODO: create the authorization-specific models
# class Review(models.Model):
#     pass
