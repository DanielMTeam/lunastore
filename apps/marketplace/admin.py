from django.contrib import admin
from .models import *
from .forms import AppScreenshotForm 
from django.conf import settings
from django.utils.html import format_html


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
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
class DistributionAdmin(admin.ModelAdmin):
    pass
