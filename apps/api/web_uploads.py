from django.urls import path
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from apps.api.v2.views import UserViewSet


def session_upload(action):
    view = UserViewSet.as_view(
        {"get": action},
        authentication_classes=(SessionAuthentication,),
        permission_classes=(IsAuthenticated,),
    )
    return never_cache(view)


urlpatterns = [
    path("public/", session_upload("get_public_upload_token"), name="web-public-upload-token"),
    path("private/", session_upload("get_private_upload_token"), name="web-private-upload-token"),
]
