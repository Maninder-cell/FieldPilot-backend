"""
Tenant Membership Middleware

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import logging
from django.db import connection
from .models import TenantMember

logger = logging.getLogger(__name__)


class TenantMembershipMiddleware:
    """
    Middleware to attach current tenant membership to request.
    
    This middleware runs after TenantMainMiddleware and adds:
    - request.tenant_membership: TenantMember object for current user in current tenant
    - request.tenant_role: String role of user in current tenant (or None)
    
    This allows views to check permissions based on tenant-specific roles.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Initialize tenant membership attributes
        request.tenant_membership = None
        request.tenant_role = None
        
        # Only process for authenticated users
        if request.user.is_authenticated:
            try:
                # Get current tenant from django-tenants
                tenant = getattr(connection, 'tenant', None)
                
                if tenant and hasattr(tenant, 'schema_name'):
                    # TenantMember is in SHARED_APPS (public schema)
                    # We need to query it from public schema regardless of current schema
                    from django_tenants.utils import schema_context
                    
                    try:
                        # Always query TenantMember from public schema
                        with schema_context('public'):
                            try:
                                # Get user's membership in current tenant
                                membership = TenantMember.objects.get(
                                    tenant=tenant,
                                    user=request.user,
                                    is_active=True
                                )
                                request.tenant_membership = membership
                                request.tenant_role = membership.role
                                
                                logger.debug(
                                    f"User {request.user.email} accessing tenant {tenant.name} "
                                    f"with role {membership.role}"
                                )
                            except TenantMember.DoesNotExist:
                                # User is not a member of this specific tenant
                                # Try to get user's first active membership as fallback
                                membership = TenantMember.objects.filter(
                                    user=request.user,
                                    is_active=True
                                ).first()
                                
                                if membership:
                                    request.tenant_membership = membership
                                    request.tenant_role = membership.role
                                    logger.debug(
                                        f"User {request.user.email} using primary tenant "
                                        f"{membership.tenant.name} with role {membership.role}"
                                    )
                                else:
                                    logger.warning(
                                        f"User {request.user.email} has no active tenant memberships"
                                    )
                    except Exception as e:
                        logger.error(f"Error querying tenant membership: {str(e)}", exc_info=True)
            except Exception as e:
                logger.error(f"Error in TenantMembershipMiddleware: {str(e)}", exc_info=True)
        
        response = self.get_response(request)
        return response
