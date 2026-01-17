# url configuration for marketplace app
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('index.php', views.marketplace, name='index'),
    path('category.php', views.category, name='category'),
    path('app.php', views.app, name='app'),
    path('faq.php', views.faq, name='faq'),
    path('app_add.php', views.app_add, name='app_add'),
    path('settings_apps.php', views.settings_apps, name='settings_apps'),
]
