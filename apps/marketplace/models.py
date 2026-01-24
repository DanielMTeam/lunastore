from django.db import models
from django.conf import settings
import uuid, os
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramSimilarity

def get_icon_path(instance,filename):
    # for application model
    ext = filename.split('.')[-1]
    filename=f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('ugc/app_icons',filename)

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

class BaseApplicationInfo(models.Model):
    category = models.ForeignKey('Category', null=True, on_delete=models.SET_NULL, verbose_name="Категория")
    title = models.CharField(max_length=80, verbose_name="Название")
    description = models.CharField(max_length=1400, verbose_name="Описание")
    slogan = models.CharField(max_length=240, null=True, blank=True, verbose_name="Слоган")
    icon = models.ImageField(upload_to=get_icon_path, max_length=140, null=True, verbose_name="Иконка")
    price = models.IntegerField(default=0, verbose_name="Цена")
    screenshots = models.JSONField(default=list, blank=True, null=True, verbose_name="Скриншоты")
    developer_site = models.URLField(max_length=160, null=True, blank=True, verbose_name="Сайт разработчика")

    class Meta:
        abstract = True

class Application(BaseApplicationInfo):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications', verbose_name="Автор")
    
    is_demo = models.BooleanField(default=False)
    is_under_dmca = models.BooleanField(default=False)
    published = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Приложение"
        verbose_name_plural = "Приложения"
        permissions = [
            ("set_dmca_flag", "Can set DMCA flag on application"),
            ("set_demo_flag", "Can set demo flag on application"),
        ]
        indexes = [
            GinIndex(
                name='app_trgm_idx',
                fields=['title','description','slogan'],
                opclasses=['gin_trgm_ops','gin_trgm_ops','gin_trgm_ops']
            ),
        ]

    def __str__(self):
        return self.title


class Distribution(models.Model):
    app = models.ForeignKey(Application, on_delete=models.PROTECT)
    version = models.CharField(max_length=20)
    file = models.FileField(upload_to='ugc/distributions',max_length=80, null=True)
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
    
class AppCreateRequests(BaseApplicationInfo):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='create_requests',
        verbose_name="Автор заявки"
    )
    
    status_choices = (
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='pending', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Заявка на создание"
        verbose_name_plural = "Заявки на создание"

class AppEditRequests(BaseApplicationInfo):
    target_application = models.ForeignKey(
        Application, 
        on_delete=models.CASCADE,
        related_name='edit_requests',
        verbose_name="Редактируемое приложение"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='edit_requests_author', 
        verbose_name="Автор правки"
    )
    status_choices = (
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='pending', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Заявка на изменение"
        verbose_name_plural = "Заявки на изменения"

# TODO: create the authorization-specific models
# class Review(models.Model):
#     pass
