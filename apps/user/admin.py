from django.contrib import admin
from .models import User, UserBan
from .forms import user_ban

# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'email',
                       'password', 'avatar', 'role')
        }),
        ('Дополнительная информация', {
            'fields': ('telegram', 'discord', 'website')
        })
    )
    
    list_display = ['username', 'email', 'role', 'avatar']
    list_filter = ['role']
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