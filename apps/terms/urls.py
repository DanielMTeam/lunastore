# url configuration for terms (lunastore terms pages) app
from django.urls import path

from . import views

urlpatterns = [
    path("other_projects.php", views.other_projects, name="other_projects"),
    path("help_center.php", views.help_center, name="help_center"),
]
