# url configuration for marketplace app
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('index.php', views.marketplace, name='index'),
    path('category.php', views.category, name='category'),
    path('app.php', views.app, name='app'),
    path('download.php', views.download_list, name='download_list'),
    path('faq.php', views.faq, name='faq'),
    path('app_add.php', views.app_add, name='app_add'),
    path('settings_apps.php', views.settings_apps, name='settings_apps'),
    path('edit_app_info.php/<int:pk>/', views.application_edit_info, name='edit_app_info'),
    path('distributions.php', views.manage_distributions, name='manage_distributions'),
    path('distribution_edit.php/<int:dist_pk>/', views.distribution_edit, name='distribution_edit'),
    path('distribution_delete.php/<int:dist_pk>/', views.distribution_delete, name='distribution_delete'),
    path('search.php', views.search, name='search'),
    path('report_app.php', views.report_app, name='report_app')
]
