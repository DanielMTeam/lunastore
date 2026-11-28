from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import account, batch, catalog

router = SimpleRouter()
router.register("apps", catalog.ApplicationViewSet, basename="v3-app")
router.register("categories", catalog.CategoryViewSet, basename="v3-category")
router.register("collections", catalog.CollectionViewSet, basename="v3-collection")
router.register("distributions", catalog.DistributionViewSet, basename="v3-distribution")
router.register("platforms", catalog.PlatformViewSet, basename="v3-platform")
router.register("users", catalog.UserViewSet, basename="v3-user")

urlpatterns = [
    path("batch/", batch.BatchView.as_view(), name="v3-batch"),
    path("auth/token/", account.TokenObtainView.as_view(), name="v3-token-obtain"),
    path("auth/token/refresh/", account.TokenRotateView.as_view(), name="v3-token-refresh"),
    path("auth/token/revoke/", account.TokenRevokeView.as_view(), name="v3-token-revoke"),
    path("me/", account.MeView.as_view(), name="v3-me"),
    path("me/notifications/", account.NotificationsView.as_view(), name="v3-notifications"),
    path("me/notifications/mark-all-read/", account.MarkNotificationsReadView.as_view(), name="v3-notifications-read"),
    path("health/", catalog.HealthView.as_view(), name="v3-health"),
    path("search/suggestions/", catalog.SuggestionView.as_view(), name="v3-suggestions"),
    path("", include(router.urls)),
]
