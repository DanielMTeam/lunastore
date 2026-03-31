from django.db import models


def get_file_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return os.path.join("sidebar_pics/", new_filename)


class Banner(models.Model):
    title = models.CharField(max_length=100, verbose_name="Название (для себя)")
    image = models.ImageField(upload_to="otherdata/", verbose_name="Изображение")
    url = models.URLField(
        verbose_name="Ссылка", blank=True, help_text="Куда ведет клик"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"

    def __str__(self):
        return self.title
