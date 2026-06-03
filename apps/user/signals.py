import logging
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.marketplace.models import Application, Category, Distribution
from .models import UserBan
from .tasks import refresh_banned_ips_cache

User = settings.AUTH_USER_MODEL
log = logging.getLogger("user")


@receiver([post_save, post_delete], sender=UserBan)
def update_ipban_cache(sender: type, **kwargs: Any) -> None:
    # update ip ban cache on save or delete of userban
    log.info("[signal apps.user] 'UserBanForm' model changed, refreshing banned IPs cache...")
    refresh_banned_ips_cache.enqueue()


@receiver(post_save, sender=User)
def kick_from_session_on_ban(sender: type, instance: Any, created: bool, **kwargs: Any) -> None:
    # kick user from active sessions if they are banned
    if not created and not instance.is_active:
        deleted_sessions = 0
        for session in Session.objects.all():
            session_data = session.get_decoded()
            if session_data.get('_auth_user_id') == str(instance.id):
                session.delete()
                deleted_sessions += 1

from django.contrib.auth.signals import user_logged_out

@receiver(user_logged_out)
def remove_user_session(sender, request, user, **kwargs):
    if request and request.session.session_key:
        from .models import UserSession
        UserSession.objects.filter(session_key=request.session.session_key).delete()

def create_groups(sender: AppConfig, **kwargs: Any) -> None:
    # moderator group
    moderator_group, created = Group.objects.get_or_create(name='Модераторы')
    if created:
        log.info("moderators group created")
    
    try:
        category_ct = ContentType.objects.get_for_model(Category)
        app_ct = ContentType.objects.get_for_model(Application)
        distribution_ct = ContentType.objects.get_for_model(Distribution)
        ban_ct = ContentType.objects.get_for_model(UserBan)
        permissions = [
            # category model permissions
            Permission.objects.get(codename='view_category', content_type=category_ct),
            # application model permissions
            Permission.objects.get(codename='view_application', content_type=app_ct),
            Permission.objects.get(codename='change_application', content_type=app_ct),
            Permission.objects.get(codename='delete_application', content_type=app_ct),
            Permission.objects.get(codename='add_application', content_type=app_ct),
            Permission.objects.get(codename='set_dmca_flag', content_type=app_ct),
            Permission.objects.get(codename='set_demo_flag', content_type=app_ct),
            # distribution model permissions
            Permission.objects.get(codename='view_distribution', content_type=distribution_ct),
            Permission.objects.get(codename='change_distribution', content_type=distribution_ct),
            Permission.objects.get(codename='delete_distribution', content_type=distribution_ct),
            Permission.objects.get(codename='add_distribution', content_type=distribution_ct),
            # userban model permissions
            Permission.objects.get(codename='view_userban', content_type=ban_ct),
            Permission.objects.get(codename='change_userban', content_type=ban_ct),
            Permission.objects.get(codename='delete_userban', content_type=ban_ct),
            Permission.objects.get(codename='add_userban', content_type=ban_ct),
        ]
        moderator_group.permissions.set(permissions)
        log.info("permissions assigned to 'Moderators' group")
    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        log.error(f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")
            
    developer_group, created = Group.objects.get_or_create(name='Разработчики')
    if created:
        log.info("developers group created")
        
    try:
        app_ct = ContentType.objects.get_for_model(Application)
        distribution_ct = ContentType.objects.get_for_model(Distribution)
        permissions = [
            # application model permissions
            Permission.objects.get(codename='add_application', content_type=app_ct),
            Permission.objects.get(codename='change_application', content_type=app_ct),
            Permission.objects.get(codename='delete_application', content_type=app_ct),
            
            # distribution model permissions
            Permission.objects.get(codename='add_distribution', content_type=distribution_ct),
            Permission.objects.get(codename='change_distribution', content_type=distribution_ct),
            Permission.objects.get(codename='delete_distribution', content_type=distribution_ct)
        ]
        developer_group.permissions.set(permissions)
        log.info("permissions assigned to 'Developers' group")
    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        log.error(f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")      
        
    user_group, created = Group.objects.get_or_create(name='Пользователи')
    if created:
        # there is no permissions for users group yet ¯\_(ツ)_/¯
        log.info("users group created")
