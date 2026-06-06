from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Внутренний контент"

    def ready(self) -> None:
        import apps.core.signals  # noqa: F401
        import apps.core.constance_sync  # noqa: F401 — register constance → .env sync
