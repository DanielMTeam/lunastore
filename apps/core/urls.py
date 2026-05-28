# url configuration for core (lunastore core pages) app
from django.urls import path
from django.views.i18n import JavaScriptCatalog

from . import views

urlpatterns = [
    path("theme_switch.php", views.theme_switch, name="theme_switch"),
    path("debug_info.php", views.debug_info, name="debug_info"),
    path(
        "set-lang/<str:lang_code>/",
        views.force_language_change,
        name="force_language_change",
    ),
    path('jsi18n/', JavaScriptCatalog.as_view(domain='django'), name='javascript-catalog'),
]
