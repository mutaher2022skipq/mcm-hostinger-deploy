from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('mark-read/<int:notif_id>/', views.mark_as_read, name='mark_as_read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
]
