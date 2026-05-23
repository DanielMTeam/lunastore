from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("method/", include("apps.api.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]

if settings.DEBUG:
    # swagger ui will work only in debug mode ^_~
    urlpatterns.append(
        path("", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui")
    )
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
