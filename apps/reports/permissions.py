"""
Reports Permissions

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.permissions import BasePermission


class IsAdminOrManager(BasePermission):
    """
    Permission class that only allows admin and manager roles to access reports.
    """
    
    def has_permission(self, request, view):
        """
        Check if user has admin or manager role.
        """
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'manager']
        )
    
    message = 'Only administrators and managers can access reports.'
