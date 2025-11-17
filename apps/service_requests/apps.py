"""
Service Requests App Configuration

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.apps import AppConfig


class ServiceRequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.service_requests'
    verbose_name = 'Service Requests'
    
    def ready(self):
        """Import signals when app is ready."""
        import apps.service_requests.signals
