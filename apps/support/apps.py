from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.support'
    verbose_name = _('PAGE_SUPPORT_TITLE')

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(grant_moderator_permissions, sender=self,
                             dispatch_uid='support.grant_moderator_permissions')


def grant_moderator_permissions(sender, using, **kwargs):
    from django.contrib.auth.management import create_permissions
    from django.contrib.auth.models import Group, Permission
    create_permissions(sender, using=using, verbosity=0)
    group = Group.objects.using(using).filter(name='Модераторы').first()
    if group:
        permissions = Permission.objects.using(using).filter(content_type__app_label='support',
                                                             codename__in=['view_ticket', 'process_ticket'])
        group.permissions.add(*permissions)
