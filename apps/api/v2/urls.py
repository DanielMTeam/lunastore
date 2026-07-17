from .views import CustomTokenObtainPairView, CustomTokenRefreshView
from django.urls import path, include
from rest_framework_simplejwt.views import TokenBlacklistView
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    MarketplaceViewSet,
    CategoryViewSet,
    ServiceViewSet,
    DistributionViewSet,
    ExecuteView
)

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='v2-user')
router.register(r'marketplace', MarketplaceViewSet, basename='v2-marketplace')
router.register(r'category', CategoryViewSet, basename='v2-category')
router.register(r'service', ServiceViewSet, basename='v2-service')
router.register(r'distribution', DistributionViewSet, basename='v2-distribution')


urlpatterns = [
    path('execute/', ExecuteView.as_view(), name='v2-execute'),
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/revoke/', TokenBlacklistView.as_view(), name='token_revoke'),
    path('', include(router.urls)),
]
