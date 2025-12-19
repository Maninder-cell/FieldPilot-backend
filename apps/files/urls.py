"""
Files URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

app_name = 'files'

urlpatterns = [
    # File management
    path('', views.file_list_create, name='file-list-create'),
    path('<uuid:file_id>/', views.file_detail, name='file-detail'),
    path('<uuid:file_id>/attach/', views.attach_file, name='attach-file'),
    path('<uuid:file_id>/detach/', views.detach_file, name='detach-file'),
    
    # File sharing
    path('shares/', views.file_share_list_create, name='file-share-list-create'),
    path('shares/<uuid:share_id>/', views.file_share_delete, name='file-share-delete'),
    path('shared/<str:share_token>/', views.shared_file_access, name='shared-file-access'),
]
