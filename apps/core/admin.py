from django.contrib import admin
from django.utils.html import format_html

from lunastore.mixins import SafeDeleteAdmin

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
