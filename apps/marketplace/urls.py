# url configuration for marketplace app
from django.urls import path
from . import views

urlpatterns = [
    path('', views.marketplace, name='index.php')
]
