"""
Core Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db import connection
from django.core.cache import cache
from django.shortcuts import render
from .responses import success_response, error_response


from drf_spectacular.utils import extend_schema


@extend_schema(
    tags=['Health'],
    summary='Health check',
    description='System health monitoring endpoint to check database and cache connectivity'
)
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



def swagger_landing(request):
    """
    Landing page for API documentation with links to Public and Tenant schemas
    """
    context = {
        'host': request.get_host(),
        'scheme': 'https' if request.is_secure() else 'http',
    }
    return render(request, 'swagger_landing.html', context)
