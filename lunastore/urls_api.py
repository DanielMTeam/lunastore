from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def api_handler404(request, exception=None):
    return JsonResponse({"detail": "Not found."}, status=404)


def api_handler500(request):
    return JsonResponse({"detail": "Internal server error."}, status=500)


def api_handler400(request, exception=None):
    return JsonResponse({"detail": "Bad request."}, status=400)


def api_handler403(request, exception=None):
    return JsonResponse({"detail": "Permission denied."}, status=403)


handler400 = "lunastore.urls_api.api_handler400"
handler403 = "lunastore.urls_api.api_handler403"
handler404 = "lunastore.urls_api.api_handler404"
handler500 = "lunastore.urls_api.api_handler500"

urlpatterns = [
    path(
        "favicon.ico",
        lambda r: HttpResponse(status=204),
    ),
    path(
        "robots.txt",
        lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain"),
    ),
    path(
        "method/",
        include("apps.api.urls"),
    ),
    path(
        "v2/",
        include("apps.api.v2.urls"),
    ),
    path(
        "schema/",
        SpectacularAPIView.as_view(),
        name="schema"),
    path(
        "",
        SpectacularSwaggerView.as_view(
            url_name="schema"),
        name="swagger-ui"),
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
