from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from .models import UserBan 
from apps.marketplace.models import Category, Application, Distribution
from django.contrib.contenttypes.models import ContentType

def create_groups(sender, **kwargs):
    # 'Moderator' group
    moderator_group, created = Group.objects.get_or_create(name='Модераторы')
    
    if created:
        print("moderators group created")
        try:
            category_ct = ContentType.objects.get_for_model(Category)
            app_ct = ContentType.objects.get_for_model(Application)
            distribution_ct = ContentType.objects.get_for_model(Distribution)
            ban_ct = ContentType.objects.get_for_model(UserBan)
            permissions = [
                # 'Category' model permissions
                Permission.objects.get(codename='view_category', content_type=category_ct),
                
                # 'Application' model permissions
                Permission.objects.get(codename='view_application', content_type=app_ct),
                Permission.objects.get(codename='change_application', content_type=app_ct),
                Permission.objects.get(codename='delete_application', content_type=app_ct),
                Permission.objects.get(codename='add_application', content_type=app_ct),
                Permission.objects.get(codename='set_dmca_flag', content_type=app_ct),
                Permission.objects.get(codename='set_demo_flag', content_type=app_ct),
                
                # 'Distribution' model permissions
                Permission.objects.get(codename='view_distribution', content_type=distribution_ct),
                Permission.objects.get(codename='change_distribution', content_type=distribution_ct),
                Permission.objects.get(codename='delete_distribution', content_type=distribution_ct),
                Permission.objects.get(codename='add_distribution', content_type=distribution_ct),

                # 'UserBan' model permissions
                Permission.objects.get(codename='view_userban', content_type=ban_ct),
                Permission.objects.get(codename='change_userban', content_type=ban_ct),
                Permission.objects.get(codename='delete_userban', content_type=ban_ct),
                Permission.objects.get(codename='add_userban', content_type=ban_ct),
            ]
            moderator_group.permissions.set(permissions)
            print("permissions assigned to 'Moderators' group")
        except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
            print(f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")
            
    developer_group, created = Group.objects.get_or_create(name='Разработчики')
    
    if created:
        print("developers group created")
        try:
            app_ct = ContentType.objects.get_for_model(Application)
            distribution_ct = ContentType.objects.get_for_model(Distribution)
            permissions = [
                # 'Application' model permissions
                Permission.objects.get(codename='add_application', content_type=app_ct),
                Permission.objects.get(codename='change_application', content_type=app_ct),
                Permission.objects.get(codename='delete_application', content_type=app_ct),
                
                # 'Distribution' model permissions
                Permission.objects.get(codename='add_distribution', content_type=distribution_ct),
                Permission.objects.get(codename='change_distribution', content_type=distribution_ct),
                Permission.objects.get(codename='delete_distribution', content_type=distribution_ct),
            ]
            developer_group.permissions.set(permissions)
            print("permissions assigned to 'Developers' group")
        except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
            print(f"Error assigning permissions. Maybe models or permissions was not created? Log: {e}")
            
    user_group, created = Group.objects.get_or_create(name='Пользователи')
    if created:
        # there is no permissions for users group yet ¯\_(ツ)_/¯
        print("users group created")