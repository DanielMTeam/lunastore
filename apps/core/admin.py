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
        "action_flag",
        "object_repr"
    )

    list_filter = (
        "action_time",
        "user",
        "content_type",
        "action_flag"
    )

    search_fields = ("object_repr", "change_message")
    date_hierarchy = "action_time"

    # protect from edit
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
