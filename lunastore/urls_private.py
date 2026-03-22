from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# configure admin panel
admin.site.site_header = "Панель LunaStore"
admin.site.site_title = "LunaStore Admin"
admin.site.index_title = "Модерация сайта"

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path("oidc/", include("mozilla_django_oidc.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
