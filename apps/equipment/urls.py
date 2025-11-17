"""
Equipment URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

app_name = 'equipment'

urlpatterns = [
    # Equipment endpoints
    path('equipment/', views.equipment_list_create, name='equipment-list-create'),
    path('equipment/<uuid:equipment_id>/', views.equipment_detail, name='equipment-detail'),
    path('equipment/<uuid:equipment_id>/history/', views.equipment_history, name='equipment-history'),
]