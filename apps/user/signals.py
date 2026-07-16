from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.contrib.auth.signals import user_logged_out
from django.core.cache import cache
from django.contrib.admin.models import LogEntry, CHANGE
from .utils import CACHE_KEY_BLACKLIST
import logging
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.marketplace.models import (
    Application, Category, Distribution,
    AppCreateRequests, AppEditRequests,
    DistributionCreateRequests, DistributionEditRequests,
    AppReportRequests, ProblemReportRequests
)
from .models import UserBan, BlacklistedUsername, DevRequestsModel
from .tasks import refresh_banned_ips_cache

User = settings.AUTH_USER_MODEL
log = logging.getLogger("user")


@receiver([post_save, post_delete], sender=UserBan)
def update_ipban_cache(sender: type, **kwargs: Any) -> None:
    # update ip ban cache on save or delete of userban
    log.info(
        "[signal apps.user] 'UserBanForm' model changed, refreshing banned IPs cache...")
    refresh_banned_ips_cache.enqueue()


@receiver([post_save, post_delete], sender=BlacklistedUsername)
def update_blacklist_cache(sender: type, **kwargs: Any) -> None:
    log.info(
        "[signal apps.user] 'BlacklistedUsername' model changed, clearing cache...")
    cache.delete(CACHE_KEY_BLACKLIST)


@receiver(post_save, sender=User)
def kick_from_session_on_ban(
        sender: type,
        instance: Any,
        created: bool,
        **kwargs: Any) -> None:
    # kick user from active sessions if they are banned
    if not created and not instance.is_active:
        from apps.core.utils import force_logout
        force_logout(instance)


@receiver(user_logged_out)
def remove_user_session(sender, request, user, **kwargs):
    if request and request.session.session_key:
        from .models import UserSession
        UserSession.objects.filter(
            session_key=request.session.session_key).delete()


def create_groups(sender: AppConfig, **kwargs: Any) -> None:
    # moderator group
    moderator_group, created = Group.objects.get_or_create(name='Модераторы')
    if created:
        log.info("moderators group created")

    try:
        category_ct = ContentType.objects.get_for_model(Category)
        app_ct = ContentType.objects.get_for_model(Application)
        distribution_ct = ContentType.objects.get_for_model(Distribution)
        from django.contrib.auth import get_user_model
        user_ct = ContentType.objects.get_for_model(get_user_model())
        ban_ct = ContentType.objects.get_for_model(UserBan)
        app_create_req_ct = ContentType.objects.get_for_model(
            AppCreateRequests)
        app_edit_req_ct = ContentType.objects.get_for_model(AppEditRequests)
        dist_create_req_ct = ContentType.objects.get_for_model(
            DistributionCreateRequests)
        dist_edit_req_ct = ContentType.objects.get_for_model(
            DistributionEditRequests)
        app_report_ct = ContentType.objects.get_for_model(AppReportRequests)
        problem_report_ct = ContentType.objects.get_for_model(
            ProblemReportRequests)
        dev_req_ct = ContentType.objects.get_for_model(DevRequestsModel)
        permissions = [
            # category model permissions
            Permission.objects.get(
                codename='view_category',
                content_type=category_ct),
            # application model permissions
            Permission.objects.get(
                codename='view_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='change_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='delete_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='add_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='set_dmca_flag',
                content_type=app_ct),
            Permission.objects.get(
                codename='set_demo_flag',
                content_type=app_ct),
            # distribution model permissions
            Permission.objects.get(
                codename='view_distribution',
                content_type=distribution_ct),
            Permission.objects.get(
                codename='change_distribution',
                content_type=distribution_ct),
            Permission.objects.get(
                codename='delete_distribution',
                content_type=distribution_ct),
            Permission.objects.get(
                codename='add_distribution',
                content_type=distribution_ct),
            # userban model permissions
            Permission.objects.get(
                codename='view_userban',
                content_type=ban_ct),
            Permission.objects.get(
                codename='change_userban',
                content_type=ban_ct),
            Permission.objects.get(
                codename='delete_userban',
                content_type=ban_ct),
            Permission.objects.get(
                codename='add_userban',
                content_type=ban_ct),

            # requests permissions
            Permission.objects.get(
                codename='view_appcreaterequests',
                content_type=app_create_req_ct),
            Permission.objects.get(
                codename='change_appcreaterequests',
                content_type=app_create_req_ct),
            Permission.objects.get(
                codename='delete_appcreaterequests',
                content_type=app_create_req_ct),

            Permission.objects.get(
                codename='view_appeditrequests',
                content_type=app_edit_req_ct),
            Permission.objects.get(
                codename='change_appeditrequests',
                content_type=app_edit_req_ct),
            Permission.objects.get(
                codename='delete_appeditrequests',
                content_type=app_edit_req_ct),

            Permission.objects.get(
                codename='view_distributioncreaterequests',
                content_type=dist_create_req_ct),
            Permission.objects.get(
                codename='change_distributioncreaterequests',
                content_type=dist_create_req_ct),
            Permission.objects.get(
                codename='delete_distributioncreaterequests',
                content_type=dist_create_req_ct),

            Permission.objects.get(
                codename='view_distributioneditrequests',
                content_type=dist_edit_req_ct),
            Permission.objects.get(
                codename='change_distributioneditrequests',
                content_type=dist_edit_req_ct),
            Permission.objects.get(
                codename='delete_distributioneditrequests',
                content_type=dist_edit_req_ct),

            Permission.objects.get(
                codename='view_devrequestsmodel',
                content_type=dev_req_ct),
            Permission.objects.get(
                codename='change_devrequestsmodel',
                content_type=dev_req_ct),
            Permission.objects.get(
                codename='delete_devrequestsmodel',
                content_type=dev_req_ct),

            # reports permissions
            Permission.objects.get(
                codename='view_appreportrequests',
                content_type=app_report_ct),
            Permission.objects.get(
                codename='change_appreportrequests',
                content_type=app_report_ct),
            Permission.objects.get(
                codename='delete_appreportrequests',
                content_type=app_report_ct),

            Permission.objects.get(
                codename='view_problemreportrequests',
                content_type=problem_report_ct),
            Permission.objects.get(
                codename='change_problemreportrequests',
                content_type=problem_report_ct),
            Permission.objects.get(
                codename='delete_problemreportrequests',
                content_type=problem_report_ct),

            # user permissions (read-only)
            Permission.objects.get(codename='view_user', content_type=user_ct),
        ]
        moderator_group.permissions.set(permissions)
        log.info("permissions assigned to 'Moderators' group")
    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        log.error(
            f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")

    developer_group, created = Group.objects.get_or_create(name='Разработчики')
    if created:
        log.info("developers group created")

    try:
        app_ct = ContentType.objects.get_for_model(Application)
        distribution_ct = ContentType.objects.get_for_model(Distribution)
        permissions = [
            # application model permissions
            Permission.objects.get(
                codename='add_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='change_application',
                content_type=app_ct),
            Permission.objects.get(
                codename='delete_application',
                content_type=app_ct),

            # distribution model permissions
            Permission.objects.get(
                codename='add_distribution',
                content_type=distribution_ct),
            Permission.objects.get(
                codename='change_distribution',
                content_type=distribution_ct),
            Permission.objects.get(
                codename='delete_distribution',
                content_type=distribution_ct)
        ]
        developer_group.permissions.set(permissions)
        log.info("permissions assigned to 'Developers' group")
    except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
        log.error(
            f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")

    user_group, created = Group.objects.get_or_create(name='Пользователи')
    if created:
        # there is no permissions for users group yet ¯\_(ツ)_/¯
        log.info("users group created")


@receiver(user_logged_in)
def log_moderator_login(sender, request, user, **kwargs):
    try:
        from constance import config
        if not getattr(config, 'LOG_MODERATOR_LOGINS', False):
            return

        if user.is_superuser or user.is_staff or user.groups.filter(
                name='Модераторы').exists():
            from apps.core.utils import get_client_ip
            ip_address = get_client_ip(request) if request else 'Unknown IP'

            LogEntry.objects.create(
                user_id=user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=str(user.id),
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Вход в систему (IP: {ip_address})"
            )
    except Exception as e:
        log.error(f"Failed to log moderator login: {e}")


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    try:
        from constance import config
        if not getattr(config, 'LOG_MODERATOR_LOGINS', False):
            return

        username = credentials.get('username')
        if not username:
            return

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        user = UserModel.objects.filter(username=username).first()
        if user and (
            user.is_superuser or user.is_staff or user.groups.filter(
                name='Модераторы').exists()):
            from apps.core.utils import get_client_ip
            ip_address = get_client_ip(request) if request else 'Unknown IP'

            LogEntry.objects.create(
                user_id=user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=str(user.id),
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Неудачная попытка входа (IP: {ip_address})"
            )
    except Exception as e:
        log.error(f"Failed to log failed login: {e}")
