"""
Reports URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Report generation
    path('generate/', views.generate_report, name='generate-report'),
    path('<uuid:report_id>/', views.report_detail, name='report-detail'),
    path('<uuid:report_id>/export/pdf/', views.export_pdf, name='export-pdf'),
    path('<uuid:report_id>/export/excel/', views.export_excel, name='export-excel'),
    
    # Report types
    path('types/', views.report_types_list, name='report-types'),
    path('types/<str:report_type>/', views.report_type_detail, name='report-type-detail'),
    
    # Scheduled reports
    path('schedules/', views.schedule_list_create, name='schedule-list-create'),
    path('schedules/<uuid:schedule_id>/', views.schedule_detail, name='schedule-detail'),
    
    # Audit
    path('audit/', views.audit_list, name='audit-list'),
]
