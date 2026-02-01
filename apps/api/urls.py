from django.urls import path, include 
from rest_framework.routers import DefaultRouter
from .views import UserViewSet

user_router = DefaultRouter()
user_router.register(r'user', UserViewSet, basename='user')

urlpatterns = [
    path('', include(user_router.urls)),
]