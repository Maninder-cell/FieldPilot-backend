"""
Core Views

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db import connection
from django.core.cache import cache
from .responses import success_response, error_response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring.
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Check cache connection
        cache.set('health_check', 'ok', 10)
        cache_status = cache.get('health_check')
        
        return success_response({
            'status': 'healthy',
            'database': 'connected',
            'cache': 'connected' if cache_status == 'ok' else 'disconnected',
            'version': '1.0.0'
        })
        
    except Exception as e:
        return error_response(
            message="Health check failed",
            details={'error': str(e)},
            status_code=503
        )