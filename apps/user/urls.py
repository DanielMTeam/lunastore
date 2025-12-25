# url configuration for auth app
from django.urls import path
from . import views

urlpatterns = [
    # authorization
    path('login.php', views.login, name='login'),
    path('logout.php', views.logout, name='logout'),
    path('register.php', views.register, name='register'),
    # profile
    path('profile.php', views.profile, name='profile'),
    path('settings.php', views.profile_settings, name='settings'),
    path('dev_status.php', views.dev_status, name='dev_status'),
]