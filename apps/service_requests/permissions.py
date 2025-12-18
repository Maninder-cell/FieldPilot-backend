"""
Service Request Permissions

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import permissions
from apps.core.permissions import ensure_tenant_role


class IsCustomer(permissions.BasePermission):
    """
    Permission class to check if user is a customer.
    Task 18.1: Create permission classes
    """
    message = 'Only customers can access this endpoint.'
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is a customer."""
        ensure_tenant_role(request)
        return request.user and request.user.is_authenticated and getattr(request, 'tenant_role', None) == 'customer'


class IsAdminOrManager(permissions.BasePermission):
    """
    Permission class to check if user is admin or manager.
    Task 18.1: Create permission classes
    """
    message = 'Only admins and managers can access this endpoint.'
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is admin or manager."""
        ensure_tenant_role(request)
        return (
            request.user and 
            request.user.is_authenticated and 
            getattr(request, 'tenant_role', None) in ['admin', 'manager', 'owner']
        )


class IsRequestOwner(permissions.BasePermission):
    """
    Permission class to check if user owns the service request.
    Task 18.1: Create permission classes
    """
    message = 'You can only access your own service requests.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the service request."""
        ensure_tenant_role(request)
        tenant_role = getattr(request, 'tenant_role', None)
        
        # Admins, managers, and owners can access all requests
        if tenant_role in ['admin', 'manager', 'owner']:
            return True
        
        # Customers can only access their own requests
        return obj.customer == request.user


class IsRequestOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class to check if user owns the request or is admin/manager.
    Combines IsRequestOwner and IsAdminOrManager.
    """
    message = 'You can only access your own service requests unless you are an admin.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the request or is admin/manager."""
        ensure_tenant_role(request)
        tenant_role = getattr(request, 'tenant_role', None)
        
        # Admins, managers, and owners can access all requests
        if tenant_role in ['admin', 'manager', 'owner']:
            return True
        
        # Customers can only access their own requests
        if tenant_role == 'customer':
            return obj.customer == request.user
        
        return False


class CanModifyRequest(permissions.BasePermission):
    """
    Permission class to check if user can modify the service request.
    Customers can only modify their own pending/under_review requests.
    """
    message = 'You cannot modify this request.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user can modify the request."""
        ensure_tenant_role(request)
        tenant_role = getattr(request, 'tenant_role', None)
        
        # Admins, managers, and owners can always modify
        if tenant_role in ['admin', 'manager', 'owner']:
            return True
        
        # Customers can only modify their own requests if not yet reviewed
        if tenant_role == 'customer':
            return obj.customer == request.user and obj.can_be_modified
        
        return False


class CanViewInternalNotes(permissions.BasePermission):
    """
    Permission class to check if user can view internal notes.
    Only admins and managers can view internal notes.
    """
    message = 'You cannot view internal notes.'
    
    def has_permission(self, request, view):
        """Check if user can view internal notes."""
        ensure_tenant_role(request)
        return (
            request.user and 
            request.user.is_authenticated and 
            getattr(request, 'tenant_role', None) in ['admin', 'manager', 'owner']
        )
