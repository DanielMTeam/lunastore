from django.contrib import admin
from django.urls import path, include

# configure admin panel
admin.site.site_header = 'Панель LunaStore'
admin.site.site_title = 'LunaStore Admin'
admin.site.index_title = 'Модерация сайта'

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('oidc/', include('mozilla_django_oidc.urls')),
]
