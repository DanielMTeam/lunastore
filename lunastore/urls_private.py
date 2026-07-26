from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from dotenv import load_dotenv
from apps.core.admin_views import admin_broadcast_notification
from apps.user.admin_views import admin_nospam_mass_scan

dotenv_path = settings.BASE_DIR / ".env"
load_dotenv(dotenv_path)

# configure admin panel
admin.site.site_header = "Панель LunaStore"
admin.site.site_title = "LunaStore Admin"
admin.site.index_title = "Модерация сайта"

urlpatterns = [path(f"{settings.ADMIN_URL}/broadcast/",
                    admin.site.admin_view(admin_broadcast_notification),
                    name='broadcast'),
               path(f"{settings.ADMIN_URL}/nospam/mass-scan/",
                    admin.site.admin_view(admin_nospam_mass_scan),
                    name='admin_nospam_mass_scan'),
               path(f"{settings.ADMIN_URL}/",
                    admin.site.urls,
                    name="admin"),
               path(f"oidc/",
                    include("mozilla_django_oidc.urls")),
               path("method/",
                    include("apps.api.urls")),
               ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
