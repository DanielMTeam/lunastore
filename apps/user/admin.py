from unfold import admin as unfold_admin
from django.contrib import admin
from .models import User, UserBan, UserActivityLog, DevRequestsModel
from .forms import UserBanForm, AddToGroupForm
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.html import format_html
from unfold.decorators import action


@admin.register(User)
class UserAdmin(unfold_admin.ModelAdmin):
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
class UserBanAdmin(unfold_admin.ModelAdmin):
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


class GroupAdmin(unfold_admin.ModelAdmin):
    form = AddToGroupForm
    filter_horizontal = ['permissions']


admin.site.register(Group, GroupAdmin)
admin.site.register(UserActivityLog)


@admin.register(DevRequestsModel)
class DevRequestsAdmin(unfold_admin.ModelAdmin):
    list_display = ('id', 'user', 'github', 'mail')
    search_fields = ['github', 'mail']
    list_filter = ('id', )
    actions = ['approve_request', 'reject_request']
    actions_detail = ['approve_request', 'reject_request']
    readonly_fields = ('user_info_link', 'user', 'mail', 'github', 'about_you', 'why_you_choose_us')
    
    def user_info_link(self, obj):
        if not obj.user:
            return "No user associated"
        
        url_site = f"/profile.php?id={obj.user.id}"
        
        return format_html(
            '''
            <div style="line-height: 1.5;">
                <a href="{}" target="_blank" style="font-weight: bold;">🔗 Профиль на сайте</a><br>
                <br>
                <span style="color: #666;">Email:</span> {}<br>
                <span style="color: #666;">Юзернейм:</span> {}<br>
                <span style="color: #666;">Дата регистрации:</span> {}
            </div>
            ''',                                  
            url_site,                                        
            obj.user.email,                                  
            obj.user.username,                               
            obj.user.date_joined.strftime('%d.%m.%Y %H:%M')  
        )
    
    user_info_link.short_description = ""
    
    @action(description='Одобрить заявку', icon="check_circle", attrs={'class': 'bg-success-600 text-white'})
    def approve_request(self, request, queryset=None, object_id=None, **kwargs):
        if queryset is None:
            queryset = self.get_queryset(request).filter(pk=object_id)
        group,created=Group.objects.get_or_create(name='Разработчики')
        
        success_count = 0
        for dev_request in queryset:
            user = dev_request.user
            if user:
                user.groups.add(group)
                success_count += 1
                dev_request.delete()
        self.message_user(request, f"Успешно одобрено {success_count} заявок и добавлено в группу 'Разработчики'.", messages.SUCCESS)
        opts = self.model._meta
        return redirect(f'admin:{opts.app_label}_{opts.model_name}_changelist')
        
    @action(description='Отклонить заявку', icon="cancel", attrs={'class': 'bg-error-600 text-white'} )
    def reject_request(self, request, queryset=None, object_id=None, **kwargs):
        if queryset is None:
            queryset = self.get_queryset(request).filter(pk=object_id)
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Отклонено и удалено заявок: {count}", messages.SUCCESS)
        opts = self.model._meta
        return redirect(f'admin:{opts.app_label}_{opts.model_name}_changelist')

    fieldsets = (
        ('Основная информация по заявке', {
            'fields': ('user', 'mail', 'github', 'about_you', 'why_you_choose_us'),
            'description': 'Информация, предоставленная пользователем в заявке на статус разработчика'
        }),
        ('Информация по объекту User (пользователю)', {
            'fields': ('user_info_link',),
            'description': 'Информация о пользователе, подавшем заявку'
        })
    )
