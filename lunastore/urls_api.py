from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.api.v3.contract import problem_response
from apps.api.v3.openapi_urls import urlpatterns as v3_patterns


def api_handler404(request, exception=None):
    if request.path_info.startswith("/v3/"):
        return problem_response(404)
    return JsonResponse({"detail": "Not found."}, status=404)


def api_handler500(request):
    if request.path_info.startswith("/v3/"):
        return problem_response(500)
    return JsonResponse({"detail": "Internal server error."}, status=500)


def api_handler400(request, exception=None):
    if request.path_info.startswith("/v3/"):
        return problem_response(400)
    return JsonResponse({"detail": "Bad request."}, status=400)


def api_handler403(request, exception=None):
    if request.path_info.startswith("/v3/"):
        return problem_response(403)
    return JsonResponse({"detail": "Permission denied."}, status=403)


handler400 = "lunastore.urls_api.api_handler400"
handler403 = "lunastore.urls_api.api_handler403"
handler404 = "lunastore.urls_api.api_handler404"
handler500 = "lunastore.urls_api.api_handler500"

v2_patterns = [path("v2/", include("apps.api.v2.urls"))]

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
        "method/v2/",
        include("apps.api.v2.urls"),
    ),
    *v2_patterns,
    *v3_patterns,
    path("schema/v2/", SpectacularAPIView.as_view(patterns=v2_patterns), name="schema-v2"),
    path("schema/v3/", SpectacularAPIView.as_view(patterns=v3_patterns), name="schema-v3"),
    path("docs/v2/", SpectacularSwaggerView.as_view(url_name="schema-v2"), name="docs-v2"),
    path("docs/v3/", SpectacularSwaggerView.as_view(url_name="schema-v3"), name="docs-v3"),
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
