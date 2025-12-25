"""
Reports Permissions

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.permissions import BasePermission
from apps.core.permissions import ensure_tenant_role


class IsAdminOrManager(BasePermission):
    """
    Permission class that only allows admin and manager roles to access reports.
    """
    
    def has_permission(self, request, view):
        """
        Check if user has admin or manager role.
        """
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Ensure tenant role is set
        ensure_tenant_role(request)
        
        return getattr(request, 'tenant_role', None) in ['admin', 'manager', 'owner']
    
    message = 'Only administrators and managers can access reports.'
