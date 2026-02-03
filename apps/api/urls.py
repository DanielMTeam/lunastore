from django.urls import path, include 
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, MarketplaceViewSet, CategoryViewSet, ServiceViewSet

router = DefaultRouter()
router.register(r'user', UserViewSet, basename='user')
router.register(r'marketplace', MarketplaceViewSet, basename='marketplace')
router.register(r'category', CategoryViewSet, basename='category')
router.register(r'service', ServiceViewSet, basename='service')

urlpatterns = [
    path('', include(router.urls)),
]