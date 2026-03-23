from django.db import models


def get_file_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join("sidebar_pics/", new_filename)


class Banner(models.Model):
    title = models.CharField(max_length=100, verbose_name="Название (для себя)")
    image = models.ImageField(upload_to="banners/", verbose_name="Изображение")
    url = models.URLField(
        verbose_name="Ссылка", blank=True, help_text="Куда ведет клик"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"

    def __str__(self):
        return self.title


class LegalDocument(models.Model):
    LANGUAGE_CHOICES = (
        ("ru", "Русский"),
        ("en", "English"),
    )

    doc_type = models.CharField(
        max_length=50, default="privacy", verbose_name="Тип документа"
    )
    language = models.CharField(
        max_length=2, choices=LANGUAGE_CHOICES, verbose_name="Язык"
    )
    content = models.TextField(verbose_name="Содержание")
    last_updated = models.DateTimeField(
        auto_now=True, verbose_name="Последнее обновление"
    )

    class Meta:
        unique_together = ("doc_type", "language")
        verbose_name = "Юридический документ"
        verbose_name_plural = "Юридические документы"

    def __str__(self):
        return f"{self.doc_type} ({self.language})"
