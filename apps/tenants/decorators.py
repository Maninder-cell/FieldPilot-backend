"""
Tenant Permission Decorators

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from functools import wraps
from rest_framework import status
from apps.core.responses import error_response


def require_tenant_membership(view_func):
    """
    Decorator to ensure user is a member of the current tenant.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'tenant_membership') or request.tenant_membership is None:
            return error_response(
                message='You are not a member of this organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def require_tenant_role(*allowed_roles):
    """
    Decorator to check tenant-specific role.
    
    Usage:
        @require_tenant_role('owner', 'admin')
        def my_view(request):
            # Only owner or admin can access
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'tenant_membership') or request.tenant_membership is None:
                return error_response(
                    message='You are not a member of this organization',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            if request.tenant_membership.role not in allowed_roles:
                roles_str = ', '.join(allowed_roles)
                return error_response(
                    message=f'This action requires one of these roles: {roles_str}',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_owner_or_admin(view_func):
    """Shortcut decorator for owner/admin only actions."""
    return require_tenant_role('owner', 'admin')(view_func)


def require_manager_or_above(view_func):
    """Shortcut decorator for manager/admin/owner actions."""
    return require_tenant_role('owner', 'admin', 'manager')(view_func)


def check_tenant_permission(request, allowed_roles):
    """
    Helper function to check tenant permission.
    Returns (has_permission: bool, error_response: dict or None)
    
    Usage:
        has_permission, error = check_tenant_permission(request, ['owner', 'admin'])
        if not has_permission:
            return error
    """
    if not hasattr(request, 'tenant_membership') or request.tenant_membership is None:
        return False, error_response(
            message='You are not a member of this organization',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    if request.tenant_membership.role not in allowed_roles:
        roles_str = ', '.join(allowed_roles)
        return False, error_response(
            message=f'This action requires one of these roles: {roles_str}',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    return True, None
