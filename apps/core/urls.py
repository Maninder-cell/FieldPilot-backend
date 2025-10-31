"""
Core URLs

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.health_check, name='health_check'),
]