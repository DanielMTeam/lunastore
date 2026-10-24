from django.urls import path
from . import views

app_name = 'support'
urlpatterns = [
    path('support.php', views.ticket_list, name='list'),
    path('support_create.php', views.ticket_create, name='create'),
    path('support_ticket.php', views.ticket_detail, name='detail'),
    path('support_reply.php', views.ticket_reply, name='reply'),
    path('support_close.php', views.ticket_close, name='close'),
    path('support_updates.php', views.updates, name='updates'),
    path('support_file/<int:attachment_id>/', views.attachment_download, name='attachment'),
]
