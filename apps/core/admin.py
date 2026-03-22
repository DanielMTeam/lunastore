from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from unfold.contrib.forms.widgets import WysiwygWidget

from lunastore.mixins import SafeDeleteAdmin

from .models import Banner, LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(SafeDeleteAdmin):
    list_display = ("doc_type", "language", "last_updated")
    list_filter = ("doc_type", "language")

    search_fields = ("doc_type",)
    search_fields = ("doc_type",)

    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }


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
