from django.db import models



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
