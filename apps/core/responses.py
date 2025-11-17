"""
Standardized API Response Utilities

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone


def success_response(data=None, message=None, status_code=status.HTTP_200_OK, meta=None):
    """
    Create a standardized success response.
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        meta: Additional metadata
    
    Returns:
        Response: DRF Response object
    """
    response_data = {
        'success': True,
        'data': data,
        'meta': {
            'timestamp': timezone.now().isoformat(),
            **(meta or {})
        }
    }
    
    if message:
        response_data['message'] = message
    
    return Response(response_data, status=status_code)


def error_response(message, code=None, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Create a standardized error response.
    
    Args:
        message: Error message
        code: Error code
        details: Additional error details
        status_code: HTTP status code
    
    Returns:
        Response: DRF Response object
    """
    response_data = {
        'success': False,
        'error': {
            'code': code or 'ERROR',
            'message': message,
            'details': details or {}
        },
        'meta': {
            'timestamp': timezone.now().isoformat()
        }
    }
    
    return Response(response_data, status=status_code)


def paginated_response(queryset, serializer_class, request, message=None):
    """
    Create a paginated response.
    
    Args:
        queryset: Django queryset
        serializer_class: Serializer class
        request: Request object
        message: Optional message
    
    Returns:
        Response: Paginated response
    """
    from rest_framework.pagination import PageNumberPagination
    
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        serializer = serializer_class(page, many=True, context={'request': request})
        return paginator.get_paginated_response({
            'success': True,
            'data': serializer.data,
            'message': message,
            'meta': {
                'timestamp': timezone.now().isoformat()
            }
        })
    
    serializer = serializer_class(queryset, many=True, context={'request': request})
    return success_response(
        data=serializer.data,
        message=message
    )