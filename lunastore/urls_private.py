from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.urls import include, path
from django.views.defaults import page_not_found, server_error
from django.views.generic import RedirectView
from dotenv import load_dotenv
from apps.core.admin_views import admin_broadcast_notification
from apps.user.admin_views import admin_nospam_mass_scan

dotenv_path = settings.BASE_DIR / ".env"
load_dotenv(dotenv_path)

# configure admin panel
admin.site.site_header = "Панель LunaStore"
admin.site.site_title = "LunaStore Admin"
admin.site.index_title = "Модерация сайта"

admin_url_path = getattr(settings, "ADMIN_URL", "admin").strip("/")


def admin_handler404(request, exception=None):
    if not hasattr(request, "user"):
        request.user = AnonymousUser()
    return page_not_found(request, exception, template_name="admin/404.html")


def admin_handler500(request):
    return server_error(request, template_name="admin/500.html")


handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "lunastore.urls_private.admin_handler404"
handler500 = "lunastore.urls_private.admin_handler500"

urlpatterns = [
    path("", RedirectView.as_view(url=f"/{admin_url_path}/", permanent=False)),
    path(
        "favicon.ico",
        RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico", permanent=True),
    ),
    path(
        f"{admin_url_path}/broadcast/",
        admin.site.admin_view(admin_broadcast_notification),
        name="broadcast",
    ),
    path(
        f"{admin_url_path}/nospam/mass-scan/",
        admin.site.admin_view(admin_nospam_mass_scan),
        name="admin_nospam_mass_scan",
    ),
    path(
        f"{admin_url_path}/",
        admin.site.urls,
        name="admin",
    ),
    path(
        "oidc/",
        include("mozilla_django_oidc.urls"),
    ),
    path(
        "method/",
        include("apps.api.urls"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT,
    )
