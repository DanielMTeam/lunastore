from django.contrib import admin
from .models import User, UserBan
from .forms import user_ban, add_user_to_group   
from django.contrib.auth.models import Group

# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'email',
                       'password', 'avatar', 'is_staff', 'is_superuser'),
            'description': 'флаг is_staff является так называемым "пропуском" в админ-панель Django. флаг is_superuser дает все права без исключения. подумай дважды, прежде чем ставить эти флаги! (да блять, я серьезно)'
        }),
        ('Дополнительная информация', {
            'fields': ('telegram', 'discord', 'website')
        })
    )
    
    list_display = ['username', 'email', 'avatar']
    search_fields = ['username', 'email']
    
@admin.register(UserBan)
class UserBanAdmin(admin.ModelAdmin):
    form = user_ban
    
    list_display = ('get_username', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = ['user__username', 'reason'] 

    @admin.display(description='Пользователь', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username
    
admin.site.unregister(Group)
class GroupAdmin(admin.ModelAdmin):
    form = add_user_to_group
    filter_horizontal = ['permissions']

admin.site.register(Group, GroupAdmin)