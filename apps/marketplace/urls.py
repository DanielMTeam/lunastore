# url configuration for marketplace app
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("index.php", views.marketplace, name="index"),
    path("category.php", views.category, name="category"),
    path("app.php", views.app, name="app"),
    path("app_add.php", views.app_add, name="app_add"),
    path("settings_apps.php", views.settings_apps, name="settings_apps"),
    path(
        "edit_app_info.php/<int:pk>/", views.application_edit_info, name="edit_app_info"
    ),
    path("search.php", views.search, name="search"),
    path("report_app.php", views.report_app, name="report_app"),
]
