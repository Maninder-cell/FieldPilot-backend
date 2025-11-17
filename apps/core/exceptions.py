"""
Custom Exception Handlers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Log the exception
        logger.error(f"API Exception: {exc}", exc_info=True)
        
        # Create custom error response
        custom_response_data = {
            'success': False,
            'error': {
                'code': get_error_code(response.status_code),
                'message': get_error_message(exc, response),
                'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
            },
            'meta': {
                'timestamp': timezone.now().isoformat(),
                'path': context['request'].path if context.get('request') else None
            }
        }
        
        response.data = custom_response_data
    
    return response


def get_error_code(status_code):
    """Get error code based on HTTP status code."""
    error_codes = {
        400: 'VALIDATION_ERROR',
        401: 'UNAUTHORIZED',
        403: 'PERMISSION_DENIED',
        404: 'NOT_FOUND',
        405: 'METHOD_NOT_ALLOWED',
        409: 'CONFLICT',
        429: 'RATE_LIMIT_EXCEEDED',
        500: 'INTERNAL_SERVER_ERROR',
    }
    return error_codes.get(status_code, 'UNKNOWN_ERROR')


def get_error_message(exc, response):
    """Get user-friendly error message."""
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            # Return first error message from validation errors
            for field, errors in exc.detail.items():
                if isinstance(errors, list) and errors:
                    return f"{field}: {errors[0]}"
                return str(errors)
        return str(exc.detail)
    
    return str(exc)


class FieldRinoException(Exception):
    """Base exception for FieldRino application."""
    default_message = "An error occurred"
    default_code = "FIELDRINO_ERROR"
    
    def __init__(self, message=None, code=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class TenantNotFoundError(FieldRinoException):
    """Raised when tenant is not found."""
    default_message = "Tenant not found"
    default_code = "TENANT_NOT_FOUND"


class SubscriptionRequiredError(FieldRinoException):
    """Raised when subscription is required but not active."""
    default_message = "Active subscription required"
    default_code = "SUBSCRIPTION_REQUIRED"


class UsageLimitExceededError(FieldRinoException):
    """Raised when usage limit is exceeded."""
    default_message = "Usage limit exceeded"
    default_code = "USAGE_LIMIT_EXCEEDED"