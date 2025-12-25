from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.user'
    verbose_name = 'Аккаунт'
    
    def ready(self):
        from .signals import create_groups, update_ipban_cache
        post_migrate.connect(create_groups, sender=self)
        
