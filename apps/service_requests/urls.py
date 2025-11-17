"""
Service Requests URL Configuration

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views
from . import customer_views

app_name = 'service_requests'

urlpatterns = [
    # Customer Endpoints (Task 4)
    path('', views.service_request_list_create, name='service-request-list-create'),
    path('<uuid:request_id>/', views.service_request_detail, name='service-request-detail'),
    
    # Admin Endpoints (Task 6)
    path('admin/', views.admin_service_request_list, name='admin-service-request-list'),
    path('<uuid:request_id>/review/', views.mark_under_review, name='mark-under-review'),
    path('<uuid:request_id>/internal-notes/', views.update_internal_notes, name='update-internal-notes'),
    
    # Accept/Reject Endpoints (Task 7)
    path('<uuid:request_id>/accept/', views.accept_request, name='accept-request'),
    path('<uuid:request_id>/reject/', views.reject_request, name='reject-request'),
    
    # Task Conversion (Task 8)
    path('<uuid:request_id>/convert-to-task/', views.convert_to_task, name='convert-to-task'),
    
    # Timeline (Task 9)
    path('<uuid:request_id>/timeline/', views.request_timeline, name='request-timeline'),
    
    # Comments and Attachments (Task 10)
    path('<uuid:request_id>/comments/', views.request_comments, name='request-comments'),
    path('<uuid:request_id>/attachments/', views.request_attachments, name='request-attachments'),
    
    # Feedback
    path('<uuid:request_id>/feedback/', views.submit_feedback, name='submit-feedback'),
    
    # Reports (Task 17)
    path('reports/', views.service_request_reports, name='service-request-reports'),
    path('reports/analytics/', views.admin_dashboard_analytics, name='admin-dashboard-analytics'),
    
    # Clarifications (Task 10.2)
    path('<uuid:request_id>/clarification/', views.request_clarification, name='request-clarification'),
    path('<uuid:request_id>/clarification/respond/', views.respond_to_clarification, name='respond-to-clarification'),
]

# Customer Portal URLs (Tasks 12-13)
customer_portal_patterns = [
    # Equipment (Task 12)
    path('customer/equipment/', customer_views.customer_equipment_list, name='customer-equipment-list'),
    path('customer/equipment/<uuid:equipment_id>/', customer_views.customer_equipment_detail, name='customer-equipment-detail'),
    path('customer/equipment/<uuid:equipment_id>/history/', customer_views.customer_equipment_history, name='customer-equipment-history'),
    path('customer/equipment/<uuid:equipment_id>/upcoming/', customer_views.customer_equipment_upcoming, name='customer-equipment-upcoming'),
    
    # Dashboard (Task 13)
    path('customer/dashboard/', customer_views.customer_dashboard, name='customer-dashboard'),
]

urlpatterns += customer_portal_patterns
