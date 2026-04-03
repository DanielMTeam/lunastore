from django.contrib import admin
from django.db import models
from unfold.contrib.forms.widgets import WysiwygWidget

from lunastore.mixins import SafeDeleteAdmin

from .models import LegalDocument


# Register your models here.
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
