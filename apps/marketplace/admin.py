from unfold import admin as unfold_admin
from django.contrib import admin
from .models import *
from .forms import AppScreenshotForm 
from django.conf import settings
from django.utils.html import format_html
from unfold.decorators import action
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


@admin.register(Category)
class CategoryAdmin(unfold_admin.ModelAdmin):
    pass


@admin.register(Application)
class ApplicationAdmin(unfold_admin.ModelAdmin):
    form = AppScreenshotForm

    readonly_fields = ('display_screenshots',)
    
    screenshot_fields = [
        (f'screenshot_{i+1}', f'clear_screenshot_{i+1}') for i in range(settings.SCREENSHOT_COUNT)
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'category',
                       'description', 'slogan', 'icon', 'developer_site', 'is_demo', 'is_under_dmca', 'price')
        }),
        ('Управление скриншотами', {
            'description': 'загрузи новый файл, чтобы заменить текущий ' \
                           'или, поставь галочку "удалить", чтобы убрать скриншот',
            'fields': tuple(screenshot_fields)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        kwargs['fields'] = None
        return super().get_form(request, obj, **kwargs)
    
    def display_screenshots(self, obj):
        html = ''
        if obj.screenshots:
            prefix = '/static/'
            for path in obj.screenshots:
                html += f'<img src="{prefix}{path}" width="150" style="margin-right: 10px;" />'
        return format_html(html or "Нет скриншотов")
    display_screenshots.short_description = 'Предпросмотр'

    # boolean values

    list_display = ['title', 'category', 'is_demo', 'is_under_dmca', 'price']
    list_editable = ['is_demo', 'is_under_dmca']
    list_filter = ['is_demo', 'is_under_dmca']
    search_fields = ['title']


@admin.register(Distribution)
class DistributionAdmin(unfold_admin.ModelAdmin):
    pass

@admin.register(AppCreateRequests)
class AppCreateRequestsAdmin(unfold_admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'status')
    search_fields = ['title', 'id']
    list_filter = ('id', 'status',)
    actions = ['approve_request', 'reject_request']
    actions_detail = ['approve_request', 'reject_request']
    readonly_fields = ('user_info_link', 'user', 'status', 'category', 'title', 'description', 'slogan', 'icon_preview', 'price', 'screenshots', 'developer_site')
    
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
        
    def icon_preview(self, obj):
        if obj.icon:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="50" height="50" style="object-fit: cover; border-radius: 4px; border: 1px solid #ccc;" /></a>',
                obj.icon.url
            )
        return "Нет иконки"
    
    user_info_link.short_description = ""
    
    @action(description='Одобрить заявку', icon="check_circle", url_path='approve-request')
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)
        
        if req.status == 'approved':
            self.message_user(request, "Эта заявка уже одобрена", messages.WARNING)
            return redirect(reverse('admin:marketplace_appcreaterequests_change', args=[object_id]))

        Application.objects.create(
            user=req.user,
            category=req.category,
            title=req.title,
            description=req.description,
            slogan=req.slogan,
            price=req.price,
            icon=req.icon,
            screenshots=req.screenshots,
            developer_site=req.developer_site
        )
        
        req.status = 'approved'
        req.save()
        
        self.message_user(request, "Приложение(-ия) успешно создано!", messages.SUCCESS)
        return redirect(reverse('admin:marketplace_appcreaterequests_change', args=[object_id]))
        
    @action(description='Отклонить заявку', icon="cancel", attrs={'class': 'bg-error-600 text-white'} )
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        req.status = 'rejected'
        req.save()
        self.message_user(request, "Заявка отклонена", messages.INFO)
        return redirect(reverse('admin:marketplace_appcreaterequests_change', args=[object_id]))

    fieldsets = (
        ('Основная информация по заявке', {
            'fields': ('user', 'category', 'title', 'slogan', 'description', 'price', 'icon', 'screenshots', 'developer_site'),
            'description': 'Информация, предоставленная пользователем в заявке на статус разработчика'
        }),
        ('Информация по объекту User (пользователю)', {
            'fields': ('user_info_link',),
            'description': 'Информация о пользователе, подавшем заявку'
        })
    )
    
@admin.register(AppEditRequests)
class AppEditRequestsAdmin(unfold_admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'status')
    search_fields = ['title', 'id']
    list_filter = ('id', 'status',)
    actions_detail = ['approve_request', 'reject_request']
    readonly_fields = ('user_info_link', 'user', 'status', 'category', 'title', 'description', 'slogan', 'icon_preview', 'price', 'screenshots', 'developer_site')
    
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
    
    def icon_preview(self, obj):
        icon = obj.icon
        if not icon and obj.target_application and obj.target_application.icon:
            icon = obj.target_application.icon
        if icon:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" /></a>',
                icon.url
            )
        return "Нет иконки"
    
    
    user_info_link.short_description = ""
    
    @action(description='Одобрить заявку', icon="check_circle", attrs={'class': 'bg-success-600 text-white'})
    def approve_request(self, request, object_id):
        req = self.get_object(request, object_id)
        
        if req.status == 'approved':
            self.message_user(request, "Заявка уже была одобрена", messages.WARNING)
            return redirect(reverse('admin:marketplace_appeditrequests_change', args=[object_id]))

        app = req.target_application
        if not app:
            self.message_user(request, "Ошибка: Целевое приложение не найдено (возможно, удалено)", messages.ERROR)
            return redirect(reverse('admin:marketplace_appeditrequests_change', args=[object_id]))

        app.category = req.category
        app.title = req.title
        app.description = req.description
        app.slogan = req.slogan
        app.price = req.price
        app.developer_site = req.developer_site
        
        if req.icon:
            app.icon = req.icon
        if req.screenshots:
            app.screenshots = req.screenshots
            
        app.save()
        
        req.status = 'approved'
        req.save()
        
        self.message_user(request, "Приложение успешно обновлено!", messages.SUCCESS)
        return redirect(reverse('admin:marketplace_appeditrequests_change', args=[object_id]))
        
    @action(description='Отклонить заявку', icon="cancel", attrs={'class': 'bg-error-600 text-white'} )
    def reject_request(self, request, object_id):
        req = self.get_object(request, object_id)
        req.status = 'rejected'
        req.save()
        self.message_user(request, "Заявка отклонена", messages.INFO)
        return redirect(reverse('admin:marketplace_appeditrequests_change', args=[object_id]))
    fieldsets = (
        ('Основная информация по заявке', {
            'fields': ('user', 'category', 'title', 'slogan', 'description', 'price', 'icon', 'screenshots', 'developer_site'),
            'description': 'Информация, предоставленная пользователем в заявке на статус разработчика'
        }),
        ('Информация по объекту User (пользователю)', {
            'fields': ('user_info_link',),
            'description': 'Информация о пользователе, подавшем заявку'
        })
    )