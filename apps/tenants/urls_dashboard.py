"""
Organization Dashboard URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Organization Dashboard
    path('', views.organization_dashboard, name='organization_dashboard'),
]
