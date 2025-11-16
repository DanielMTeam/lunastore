from django.contrib import admin
from .models import User, UserBan, UserActivityLog
from .forms import UserBanForm, AddToGroupForm   
from django.contrib.auth.models import Group

admin.site.site_header = "Lunastore Admin Panel"
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'email', 'description',
                       'password', 'avatar', 'is_staff', 'is_superuser', 'is_active'),
            'description': 'флаг is_staff является так называемым "пропуском" в админ-панель Django. флаг is_superuser дает все права без исключения. подумай дважды, прежде чем ставить эти флаги! (да блять, я серьезно)'
        }),
        ('Дополнительная информация', {
            'fields': ('telegram', 'discord', 'website')
        })
    )
    
    list_display = ['pk', 'username', 'email', 'avatar']
    search_fields = ['username', 'email', 'pk']
    
@admin.register(UserBan)
class UserBanAdmin(admin.ModelAdmin):
    form = UserBanForm
    list_display = ('get_username', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = ['user__username', 'reason'] 
    actions = ['unban_selected_users']

    @admin.display(description='Пользователь', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username
    
    @admin.action(description='Разблокировать пользователей')
    def unban_selected_users(self, request, queryset):
        users_unbanned_count = 0
        
        for ban_entry in queryset:
            user = ban_entry.user
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])
            ban_entry.delete()
            users_unbanned_count += 1
        
        if users_unbanned_count > 0:
            self.message_user(request, f"Успешно разблокировано {users_unbanned_count} пользователей.")
            
    
admin.site.unregister(Group)
class GroupAdmin(admin.ModelAdmin):
    form = AddToGroupForm
    filter_horizontal = ['permissions']

admin.site.register(Group, GroupAdmin)

admin.site.register(UserActivityLog)