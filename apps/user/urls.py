# url configuration for auth app
from django.urls import path

from . import views

urlpatterns = [
    # authorization
    path("login.php", views.login, name="login"),
    path("logout.php", views.logout, name="logout"),
    path("register.php", views.register, name="register"),
    # profile
    path("profile.php", views.profile, name="profile"),
    path("settings.php", views.profile_settings, name="settings"),
    path("settings_security.php", views.settings_security, name="settings_security"),
    path("settings_2fa_set.php", views.settings_2fa_set, name="settings_2fa_set"),
    path("2fa_attempt.php", views.two_factor_attempt, name="two_factor_attempt"),
    path("dev_status.php", views.dev_status, name="dev_status"),
    path("502.php", views.critical_error, name="502_error"),
    path("delete_account.php", views.delete_account, name="delete_account"),
    path("invite.php", views.invite_person, name="invite_person"),
    path("invite_code.php", views.invite_code, name="invite_code"),
    path("notifications.php", views.notifications, name="notifications"),
]
