from django.contrib import admin
from .models import *
from .forms import app_screenshot
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass



@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = app_screenshot

    readonly_fields = ('display_screenshots',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'category',
                       'description', 'slogan', 'icon', 'developer_site', 'is_demo', 'is_under_dmca', 'price')
        }),
        ('Управление скриншотами', {
            'description': 'загрузи новый файл, чтобы заменить текущий ' \
                           'или, поставь галочку "удалить", чтобы убрать скриншот',
            'fields': (
                ('screenshot1', 'clear_screenshot1'),
                ('screenshot2', 'clear_screenshot2'),
                ('screenshot3', 'clear_screenshot3'),
            )
        }),
    )

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
    list_editable = ['is_demo','is_under_dmca']
    list_filter = ['is_demo','is_under_dmca']
    search_fields = ['title']
@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    pass

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
