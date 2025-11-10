"""
Tasks URL Configuration

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Task CRUD
    path('', views.task_list_create, name='task-list-create'),
    path('<uuid:task_id>/', views.task_detail, name='task-detail'),
    
    # Task Assignment and Status
    path('<uuid:task_id>/assign/', views.task_assign, name='task-assign'),
    path('<uuid:task_id>/status/', views.task_update_status, name='task-update-status'),
    path('<uuid:task_id>/work-status/', views.task_update_work_status, name='task-update-work-status'),
    path('<uuid:task_id>/history/', views.task_history, name='task-history'),
    
    # Time Tracking
    path('<uuid:task_id>/travel/', views.task_travel, name='task-travel'),
    path('<uuid:task_id>/arrive/', views.task_arrive, name='task-arrive'),
    path('<uuid:task_id>/depart/', views.task_depart, name='task-depart'),
    path('<uuid:task_id>/lunch-start/', views.task_lunch_start, name='task-lunch-start'),
    path('<uuid:task_id>/lunch-end/', views.task_lunch_end, name='task-lunch-end'),
    path('<uuid:task_id>/time-logs/', views.task_time_logs, name='task-time-logs'),
    
    # Comments
    path('<uuid:task_id>/comments/', views.task_comments, name='task-comments'),
    path('comments/<uuid:comment_id>/', views.comment_detail, name='comment-detail'),
    
    # Attachments
    path('<uuid:task_id>/attachments/', views.task_attachments, name='task-attachments'),
    path('attachments/<uuid:attachment_id>/', views.attachment_delete, name='attachment-delete'),
    path('attachments/<uuid:attachment_id>/download/', views.attachment_download, name='attachment-download'),
    
    # Materials
    path('<uuid:task_id>/materials/needed/', views.task_materials_needed, name='task-materials-needed'),
    path('<uuid:task_id>/materials/received/', views.task_materials_received, name='task-materials-received'),
    path('<uuid:task_id>/materials/', views.task_materials, name='task-materials'),
    
    # Teams
    path('teams/', views.team_list_create, name='team-list-create'),
    path('teams/<uuid:team_id>/', views.team_detail, name='team-detail'),
    path('teams/<uuid:team_id>/members/', views.team_add_members, name='team-add-members'),
    path('teams/<uuid:team_id>/members/<uuid:member_id>/', views.team_remove_member, name='team-remove-member'),
    
    # Reports
    path('reports/work-hours/', views.work_hours_report, name='work-hours-report'),
]
