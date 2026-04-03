# url configuration for core (lunastore core pages) app
from django.urls import path

from . import views

urlpatterns = [
    path("debug_info.php", views.debug_info, name="debug_info"),
    path(
        "set-lang/<str:lang_code>/",
        views.force_language_change,
        name="force_language_change",
    ),
]
