"""
Custom Permissions

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)


# Store role permissions globally for views
_VIEW_ROLE_PERMISSIONS = {}


def method_role_permissions(**role_map):
    """
    Decorator to set role_permissions on a view function.
    Stores permissions in a global registry that MethodRolePermission can access.
    
    Usage:
        @api_view(['GET', 'POST'])
        @permission_classes([IsAuthenticated, MethodRolePermission])
        @method_role_permissions(GET=['admin', 'manager'], POST=['admin'])
        def my_view(request):
            ...
    """
    def decorator(view_func_or_class):
        # Get the function name to use as key
        func_name = getattr(view_func_or_class, '__name__', None)
        if not func_name and hasattr(view_func_or_class, '__func__'):
            func_name = view_func_or_class.__func__.__name__
        
        if func_name:
            _VIEW_ROLE_PERMISSIONS[func_name] = role_map
        
        # Also set as attribute for direct access
        view_func_or_class.role_permissions = role_map
        
        return view_func_or_class
    return decorator


def get_customer_tenant(user):
    """
    Find which tenant a customer user belongs to.
    Searches across all tenant schemas to find the customer profile.
    
    Returns:
        tuple: (tenant, customer) or (None, None) if not found
    """
    from apps.tenants.models import Tenant
    from django_tenants.utils import schema_context
    
    if not user or not user.is_authenticated:
        return None, None
    
    # Search across all active tenants
    tenants = Tenant.objects.filter(is_active=True)
    
    for tenant in tenants:
        try:
            with schema_context(tenant.schema_name):
                from apps.facilities.models import Customer
                customer = Customer.objects.filter(user=user).first()
                if customer:
                    logger.info(f"Found customer profile for {user.email} in tenant {tenant.slug}")
                    return tenant, customer
        except Exception as e:
            logger.debug(f"Error checking tenant {tenant.slug} for customer: {str(e)}")
            continue
    
    return None, None


def with_customer_tenant_context(view_func):
    """
    Decorator to ensure customer views run in the correct tenant schema context.
    This is needed for customer endpoints that may be accessed without tenant domain.
    
    For staff users (admin/manager/etc), it uses the current tenant context.
    For customer users, it finds and switches to their tenant schema.
    
    Usage:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @with_customer_tenant_context
        def customer_dashboard(request):
            ...
    """
    from functools import wraps
    from django.db import connection
    from django_tenants.utils import schema_context
    from rest_framework import status as http_status
    from apps.core.responses import error_response
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Ensure tenant role is set
        ensure_tenant_role(request)
        
        user_role = getattr(request, 'tenant_role', None)
        
        # If user is a customer, ensure we're in their tenant context
        if user_role == 'customer':
            customer_tenant = getattr(request, 'customer_tenant', None)
            
            if not customer_tenant:
                return error_response(
                    message='Customer tenant not found',
                    status_code=http_status.HTTP_404_NOT_FOUND
                )
            
            # Execute view in customer's tenant schema
            with schema_context(customer_tenant.schema_name):
                return view_func(request, *args, **kwargs)
        else:
            # For staff users, check if we have tenant context
            tenant = getattr(connection, 'tenant', None)
            if not tenant:
                return error_response(
                    message='Tenant context required',
                    status_code=http_status.HTTP_400_BAD_REQUEST
                )
            
            # Execute view in current tenant context
            return view_func(request, *args, **kwargs)
    
    return wrapper


def ensure_tenant_role(request):
    """
    Ensure tenant_role is set on request.
    This is needed because DRF authentication happens after middleware.
    Checks both TenantMember (for staff) and Customer (for customers).
    """
    if not hasattr(request, 'tenant_role') or request.tenant_role is None:
        from django.db import connection
        from apps.tenants.models import TenantMember
        from django_tenants.utils import schema_context
        
        tenant = getattr(connection, 'tenant', None)
        
        if not request.user.is_authenticated:
            logger.warning("User is not authenticated")
            return
        
        try:
            # Check TenantMember in public schema
            with schema_context('public'):
                # First try to find membership for current tenant
                if tenant:
                    membership = TenantMember.objects.filter(
                        tenant_id=tenant.id,
                        user=request.user,
                        is_active=True
                    ).first()
                else:
                    membership = None
                
                if not membership:
                    # Try user's first active membership
                    membership = TenantMember.objects.filter(
                        user=request.user,
                        is_active=True
                    ).first()
                    
                    if membership:
                        logger.info(f"Using membership from different tenant for user {request.user.email}: {membership.role}")
                
                if membership:
                    request.tenant_role = membership.role
                    request.tenant_membership = membership
                    # Also set customer_tenant for customer role
                    if membership.role == 'customer':
                        request.customer_tenant = membership.tenant
                    logger.info(f"Set tenant_role={membership.role} for user {request.user.email}")
            
            # If no membership found, check if user is a customer
            if not hasattr(request, 'tenant_role') or request.tenant_role is None:
                # If we have a tenant context, check in that schema
                if tenant:
                    try:
                        from apps.facilities.models import Customer
                        customer = Customer.objects.filter(user=request.user).first()
                        if customer:
                            request.tenant_role = 'customer'
                            request.customer_profile = customer
                            request.customer_tenant = tenant
                            logger.info(f"Set tenant_role=customer for user {request.user.email}")
                    except Exception as customer_error:
                        logger.warning(f"Error checking customer profile: {str(customer_error)}")
                else:
                    # No tenant context - search across all tenants for customer
                    customer_tenant, customer = get_customer_tenant(request.user)
                    if customer_tenant and customer:
                        request.tenant_role = 'customer'
                        request.customer_profile = customer
                        request.customer_tenant = customer_tenant
                        logger.info(f"Set tenant_role=customer for user {request.user.email} in tenant {customer_tenant.slug}")
                    else:
                        logger.warning(f"No active membership or customer profile found for user {request.user.email}")
        except Exception as e:
            logger.error(f"Error getting tenant membership: {str(e)}", exc_info=True)


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


class HasTenantRole(permissions.BasePermission):
    """
    Base permission class for tenant role-based access control.
    Subclass this and set required_roles to specify allowed roles.
    """
    required_roles = []
    
    def has_permission(self, request, view):
        ensure_tenant_role(request)
        tenant_role = getattr(request, 'tenant_role', None)
        return tenant_role in self.required_roles


class IsOwnerOnly(HasTenantRole):
    """
    Permission for owner-only access.
    """
    required_roles = ['owner']


class IsAdminOnly(HasTenantRole):
    """
    Permission for admin-only access.
    """
    required_roles = ['admin']


class IsAdminOrOwner(HasTenantRole):
    """
    Permission for admin or owner access.
    """
    required_roles = ['admin', 'owner']


class IsAdminManagerOwner(HasTenantRole):
    """
    Permission for admin, manager, or owner access.
    """
    required_roles = ['admin', 'manager', 'owner']


class IsTechnicianOnly(HasTenantRole):
    """
    Permission for technician-only access.
    """
    required_roles = ['technician']


class IsEmployeeOnly(HasTenantRole):
    """
    Permission for employee-only access.
    """
    required_roles = ['employee']


class IsStaffMember(HasTenantRole):
    """
    Permission for staff members (admin, manager, employee, technician).
    Excludes customers and requires owner/admin/manager/employee/technician role.
    """
    required_roles = ['owner', 'admin', 'manager', 'employee', 'technician']


class IsAdminManagerEmployee(HasTenantRole):
    """
    Permission for admin, manager, or employee access.
    """
    required_roles = ['admin', 'manager', 'employee', 'owner']


class IsTechnicianOrEmployee(HasTenantRole):
    """
    Permission for technician or employee access.
    """
    required_roles = ['technician', 'employee']


class IsAdminUser(permissions.BasePermission):
    """
    Permission to check if user is admin.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        ensure_tenant_role(request)
        return getattr(request, 'tenant_role', None) == 'admin'


class IsManagerOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is manager or admin.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        ensure_tenant_role(request)
        return getattr(request, 'tenant_role', None) in ['admin', 'manager', 'owner']


class IsTechnicianOrAbove(HasTenantRole):
    """
    Permission to check if user is technician, employee, manager, admin, or owner.
    This is the same as IsStaffMember - includes all staff roles.
    """
    required_roles = ['owner', 'admin', 'manager', 'employee', 'technician']


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


class MethodRolePermission(permissions.BasePermission):
    """
    Permission class that allows different roles per HTTP method.
    Define role_permissions on the view as a dict mapping methods to allowed roles.
    
    Example:
        role_permissions = {
            'GET': ['admin', 'manager', 'technician'],
            'POST': ['admin', 'manager'],
            'PUT': ['admin', 'manager'],
            'PATCH': ['admin', 'manager'],
            'DELETE': ['admin', 'owner'],
        }
    """
    
    def has_permission(self, request, view):
        ensure_tenant_role(request)
        
        # Get role permissions from view
        role_map = None
        
        # Try to get from the view instance first
        role_map = getattr(view, 'role_permissions', None)
        
        # For @api_view decorated functions, check the underlying function
        if not role_map and hasattr(view, 'cls'):
            # DRF wraps @api_view functions in a class
            # The actual function is stored in cls.{method_name}
            method_name = request.method.lower()
            handler = getattr(view.cls, method_name, None)
            if handler:
                role_map = getattr(handler, 'role_permissions', None)
        
        # Try the global registry (for function-based views)
        if not role_map:
            view_name = type(view).__name__
            role_map = _VIEW_ROLE_PERMISSIONS.get(view_name, None)
        
        # For @api_view decorated functions, check the underlying function
        if not role_map and hasattr(view, '_view_func'):
            role_map = getattr(view._view_func, 'role_permissions', None)
        
        # Try view.cls for class-based views
        if not role_map and hasattr(view, 'cls'):
            role_map = getattr(view.cls, 'role_permissions', None)
        
        if not role_map:
            role_map = {}
        
        allowed_roles = role_map.get(request.method, [])
        tenant_role = getattr(request, 'tenant_role', None)
        
        has_perm = tenant_role in allowed_roles
        if not has_perm:
            logger.warning(f"Permission denied: tenant_role '{tenant_role}' not in allowed_roles {allowed_roles} for method {request.method} (view: {type(view).__name__}, role_map: {role_map})")
        
        return has_perm


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


class IsOwnerOrAdminManager(permissions.BasePermission):
    """
    Permission for object owner or admin/manager.
    Checks if user is the owner of the object (via uploaded_by, created_by, etc.)
    or has admin/manager role.
    """
    
    def has_object_permission(self, request, view, obj):
        ensure_tenant_role(request)
        tenant_role = getattr(request, 'tenant_role', None)
        
        # Admin/manager can access
        if tenant_role in ['admin', 'manager', 'owner']:
            return True
        
        # Check if user is the owner
        owner_field = getattr(obj, 'uploaded_by', None) or getattr(obj, 'created_by', None)
        return owner_field == request.user


class IsCustomerOnly(HasTenantRole):
    """
    Permission for customer-only access.
    """
    required_roles = ['customer']
