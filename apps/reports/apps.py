"""
Reports App Configuration

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'Reports'
    
    def ready(self):
        """
        Import generators to register them when the app is ready.
        """
        # Import generators to trigger @register_report decorators
        from apps.reports import generators  # noqa
