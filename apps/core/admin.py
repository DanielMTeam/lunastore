from django.contrib import admin
from django.utils.html import format_html
from django.contrib.admin.models import LogEntry
from lunastore.mixins import SafeDeleteAdmin
from unfold.admin import ModelAdmin

from .models import Banner


@admin.register(Banner)
class BannerAdmin(SafeDeleteAdmin):
    list_display = ("title", "display_image", "is_active", "url")
    list_filter = ("is_active",)

    def display_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 40px; border-radius: 4px;" />',
                obj.image.url,
            )
        return "-"

    display_image.short_description = "Превью"

@admin.register(LogEntry)
class LoggerAdmin(ModelAdmin):
    list_display = (
        "action_time",
        "user",
        "content_type",
        "get_action_flag",
        "object_repr",
        "get_change_message"
    )

    list_filter = (
        "action_time",
        "user",
        "content_type",
        "action_flag"
    )

    search_fields = ("object_repr", "change_message", "user__username")
    date_hierarchy = "action_time"

    @admin.display(description="Действие")
    def get_action_flag(self, obj):
        from django.utils.safestring import mark_safe
        if obj.action_flag == 1:
            return mark_safe('<span style="color: green;">Добавление</span>')
        elif obj.action_flag == 2:
            return mark_safe('<span style="color: orange;">Изменение</span>')
        elif obj.action_flag == 3:
            return mark_safe('<span style="color: red;">Удаление</span>')
        return "Неизвестно"

    @admin.display(description="Детали")
    def get_change_message(self, obj):
        return obj.get_change_message()

    # protect from edit
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
