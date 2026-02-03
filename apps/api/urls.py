from django.urls import path, include 
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, MarketplaceViewSet

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')
router.register(r'marketplace', MarketplaceViewSet, basename='marketplace')

urlpatterns = [
    path('', include(router.urls)),
]