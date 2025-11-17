"""
Service Request Permissions

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import permissions


class IsCustomer(permissions.BasePermission):
    """
    Permission class to check if user is a customer.
    Task 18.1: Create permission classes
    """
    message = 'Only customers can access this endpoint.'
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is a customer."""
        return request.user and request.user.is_authenticated and request.user.role == 'customer'


class IsAdminOrManager(permissions.BasePermission):
    """
    Permission class to check if user is admin or manager.
    Task 18.1: Create permission classes
    """
    message = 'Only admins and managers can access this endpoint.'
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is admin or manager."""
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['admin', 'manager']
        )


class IsRequestOwner(permissions.BasePermission):
    """
    Permission class to check if user owns the service request.
    Task 18.1: Create permission classes
    """
    message = 'You can only access your own service requests.'
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the service request."""
        # Admins and managers can access all requests
        if request.user.role in ['admin', 'manager']:
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
        # Admins and managers can access all requests
        if request.user.role in ['admin', 'manager']:
            return True
        
        # Customers can only access their own requests
        if request.user.role == 'customer':
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
        # Admins and managers can always modify
        if request.user.role in ['admin', 'manager']:
            return True
        
        # Customers can only modify their own requests if not yet reviewed
        if request.user.role == 'customer':
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
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ['admin', 'manager']
        )
