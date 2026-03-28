import os
import re
import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from safedelete.models import SOFT_DELETE, SOFT_DELETE_CASCADE, SafeDeleteModel


def get_icon_path(instance, filename):
    # for application model
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join("ugc/app_icons", filename)


class Category(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    name = models.CharField(max_length=80)
    description = models.CharField(max_length=140)
    icon = models.CharField(
        max_length=140, null=True, blank=True, verbose_name="Иконка"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Category {self.name}>"


class BaseApplicationInfo(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    category = models.ForeignKey(
        "Category", null=True, on_delete=models.SET_NULL, verbose_name="Категория"
    )
    title = models.CharField(max_length=80, verbose_name="Название")
    original_author = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        verbose_name="Оригинальный автор",
        default="неизвестен",
    )
    description = models.CharField(max_length=1400, verbose_name="Описание")
    requirements = models.CharField(
        max_length=1400, null=True, verbose_name="Системные требования"
    )
    slogan = models.CharField(
        max_length=240, null=True, blank=True, verbose_name="Слоган"
    )
    icon_id = models.PositiveIntegerField(null=True, blank=True)
    icon_path = models.CharField(max_length=255, null=True, blank=True)
    price = models.IntegerField(default=0, verbose_name="Цена")
    screenshots = models.JSONField(
        default=list, blank=True, null=True, verbose_name="Скриншоты"
    )
    developer_site = models.URLField(
        max_length=160, null=True, blank=True, verbose_name="Сайт разработчика"
    )

    class Meta:
        abstract = True

    @property
    def icon_url(self):
        if self.icon_path:
            base_url = getattr(settings, "LUNASPIRE_URL", "").rstrip("/")
            protocol_relative_url = base_url.replace("https:", "").replace("http:", "")

            path = self.icon_path.lstrip("/")
            return f"{protocol_relative_url}/{path}"
        return "/staticfiles/img/noavatar_64.jpg"

    @property
    def screenshot_urls(self):
        base_url = getattr(settings, "LUNASPIRE_URL", "").rstrip("/")
        protocol_relative_url = base_url.replace("https:", "").replace("http:", "")

        urls = []
        for path in self.screenshots or []:
            clean_path = path.lstrip("/")
            urls.append(f"{protocol_relative_url}/{clean_path}")
        return urls


class Application(BaseApplicationInfo, SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE_CASCADE

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name="Автор",
    )

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
                name="app_trgm_idx",
                fields=["title", "description", "slogan"],
                opclasses=["gin_trgm_ops", "gin_trgm_ops", "gin_trgm_ops"],
            ),
        ]

    def __str__(self):
        return self.title


class Distribution(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    app = models.ForeignKey(Application, on_delete=models.PROTECT)
    version = models.CharField(max_length=20)
    cdn_file_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID файла в CDN"
    )
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

    @property
    def has_download(self):
        # check, can be downloaded file now
        return bool(self.cdn_file_id or self.url)

    @property
    def link(self):
        if self.cdn_file_id:
            return reverse("download_action", kwargs={"dist_pk": self.pk})
        return self.url if self.url else "#"


class AppCreateRequests(BaseApplicationInfo, SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="create_requests",
        verbose_name="Автор заявки",
    )

    status_choices = (
        ("pending", "На рассмотрении"),
        ("approved", "Одобрено"),
        ("rejected", "Отклонено"),
    )
    status = models.CharField(
        max_length=20, choices=status_choices, default="pending", verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на создание"
        verbose_name_plural = "Заявки на создание"


class AppEditRequests(BaseApplicationInfo, SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    target_application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="edit_requests",
        verbose_name="Редактируемое приложение",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="edit_requests_author",
        verbose_name="Автор правки",
    )
    status_choices = (
        ("pending", "На рассмотрении"),
        ("approved", "Одобрено"),
        ("rejected", "Отклонено"),
    )
    status = models.CharField(
        max_length=20, choices=status_choices, default="pending", verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на изменение"
        verbose_name_plural = "Заявки на изменения"


class AppReportRequests(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    REPORT_REASONS = [
        ("1", _("PAGE_REPORTAPP_REASON_MALWARE")),
        ("2", _("PAGE_REPORTAPP_REASON_INCORRECT")),
        ("3", _("PAGE_REPORTAPP_REASON_OTHER")),
    ]

    STATUS_CHOICES = [
        ("pending", "Новая"),
        ("resolved", "Рассматривается"),
        ("dismissed", "Отклонено"),
    ]

    app = models.ForeignKey(
        "Application", on_delete=models.CASCADE, related_name="reports"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("PAGE_REPORTAPP_AUTHOR"),
    )

    reason = models.CharField(max_length=1, choices=REPORT_REASONS, default="1")
    description = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Статус"
    )

    class Meta:
        verbose_name = _("PAGE_REPORTAPP_TITLE")
        verbose_name_plural = _("PAGE_REPORTAPP_TITLE_PATH")


# TODO: create the authorization-specific models
# class Review(models.Model):
#     pass
