# url configuration for marketplace app
from django.urls import path
from . import views

urlpatterns = [
    path('', views.homeRedirect, name='home'),
    path('index.php', views.marketplace, name='index.php')
]
