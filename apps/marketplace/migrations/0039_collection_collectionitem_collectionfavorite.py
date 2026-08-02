# Generated manually for collections feature (additive CreateModel only)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0038_distribution_release_description_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Collection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "deleted",
                    models.DateTimeField(db_index=True, editable=False, null=True),
                ),
                (
                    "deleted_by_cascade",
                    models.BooleanField(default=False, editable=False),
                ),
                (
                    "title",
                    models.CharField(max_length=120, verbose_name="Название"),
                ),
                (
                    "title_ru",
                    models.CharField(
                        max_length=120, null=True, verbose_name="Название"
                    ),
                ),
                (
                    "title_en",
                    models.CharField(
                        max_length=120, null=True, verbose_name="Название"
                    ),
                ),
                (
                    "title_uk",
                    models.CharField(
                        max_length=120, null=True, verbose_name="Название"
                    ),
                ),
                (
                    "title_be",
                    models.CharField(
                        max_length=120, null=True, verbose_name="Название"
                    ),
                ),
                (
                    "title_kk",
                    models.CharField(
                        max_length=120, null=True, verbose_name="Название"
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Описание"
                    ),
                ),
                (
                    "description_ru",
                    models.TextField(
                        blank=True, default="", null=True, verbose_name="Описание"
                    ),
                ),
                (
                    "description_en",
                    models.TextField(
                        blank=True, default="", null=True, verbose_name="Описание"
                    ),
                ),
                (
                    "description_uk",
                    models.TextField(
                        blank=True, default="", null=True, verbose_name="Описание"
                    ),
                ),
                (
                    "description_be",
                    models.TextField(
                        blank=True, default="", null=True, verbose_name="Описание"
                    ),
                ),
                (
                    "description_kk",
                    models.TextField(
                        blank=True, default="", null=True, verbose_name="Описание"
                    ),
                ),
                (
                    "is_system",
                    models.BooleanField(
                        default=False,
                        help_text="system likes collection; at most one per owner",
                        verbose_name="Системная коллекция",
                    ),
                ),
                (
                    "is_public",
                    models.BooleanField(default=True, verbose_name="Публичная"),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Дата обновления"
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collections",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Владелец",
                    ),
                ),
            ],
            options={
                "verbose_name": "Коллекция",
                "verbose_name_plural": "Коллекции",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="CollectionItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "added_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Добавлено"
                    ),
                ),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collection_items",
                        to="marketplace.application",
                        verbose_name="Приложение",
                    ),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="marketplace.collection",
                        verbose_name="Коллекция",
                    ),
                ),
            ],
            options={
                "verbose_name": "Элемент коллекции",
                "verbose_name_plural": "Элементы коллекций",
                "ordering": ["-added_at"],
                "unique_together": {("collection", "application")},
            },
        ),
        migrations.CreateModel(
            name="CollectionFavorite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Дата"),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to="marketplace.collection",
                        verbose_name="Коллекция",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorite_collections",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Избранная коллекция",
                "verbose_name_plural": "Избранные коллекции",
                "ordering": ["-created_at"],
                "unique_together": {("user", "collection")},
            },
        ),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted__isnull=True, is_system=True),
                fields=("owner",),
                name="uniq_system_collection_per_owner",
            ),
        ),
    ]
