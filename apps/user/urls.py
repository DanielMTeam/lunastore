# url configuration for auth app
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views
from .forms import CustomPasswordResetForm

urlpatterns = [
    # authorization
    path("login.php", views.login, name="login"),
    path("logout.php", views.logout, name="logout"),
    path("register.php", views.register, name="register"),
    # profile
    path("profile.php", views.profile, name="profile"),
    path("settings.php", views.profile_settings, name="settings"),
    path(
        "settings_security.php",
        views.settings_security,
        name="settings_security"),
    path(
        "settings_2fa_set.php",
        views.settings_2fa_set,
        name="settings_2fa_set"),
    path(
        "2fa_attempt.php",
        views.two_factor_attempt,
        name="two_factor_attempt"),
    path("dev_status.php", views.dev_status, name="dev_status"),
    path("502.php", views.critical_error, name="502_error"),
    path("delete_account.php", views.delete_account, name="delete_account"),
    path("invite.php", views.invite_person, name="invite_person"),
    path("invite_code.php", views.invite_code, name="invite_code"),
    path("notifications.php", views.notifications, name="notifications"),
    path(
        "revert_impersonation.php",
        views.revert_impersonation,
        name="revert_impersonation"),
    path(
        "terminate_session.php/<int:session_pk>/",
        views.terminate_session,
        name="terminate_session"),

    # password reset
    path(
        "password_reset.php",
        views.RateLimitedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password_reset_done.php",
        auth_views.PasswordResetDoneView.as_view(
            template_name="user/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset.php/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="user/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password_reset_complete.php",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="user/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
