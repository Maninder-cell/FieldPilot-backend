"""
Custom Permissions

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser


class IsTenantUser(permissions.BasePermission):
    """
    Permission to check if user belongs to the current tenant.
    """
    
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user belongs to current tenant
        if hasattr(request, 'tenant') and hasattr(request.user, 'tenant_id'):
            return request.user.tenant_id == request.tenant.id
        
        return True


class IsAdminUser(permissions.BasePermission):
    """
    Permission to check if user is admin.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'admin'
        )


class IsManagerOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is manager or admin.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['admin', 'manager']
        )


class IsTechnicianOrAbove(permissions.BasePermission):
    """
    Permission to check if user is technician, manager, or admin.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['admin', 'manager', 'employee', 'technician']
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to check if user is owner of object or read-only.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to owner
        return obj.created_by == request.user


class HasActiveSubscription(permissions.BasePermission):
    """
    Permission to check if tenant has active subscription.
    """
    
    def has_permission(self, request, view):
        if not hasattr(request, 'tenant'):
            return False
        
        # Check if tenant has active subscription
        from apps.billing.models import Subscription
        
        try:
            subscription = Subscription.objects.get(
                tenant=request.tenant,
                status='active'
            )
            return True
        except Subscription.DoesNotExist:
            return False