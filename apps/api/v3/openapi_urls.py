from django.urls import include, path

urlpatterns = [path("v3/", include("apps.api.v3.urls"))]
