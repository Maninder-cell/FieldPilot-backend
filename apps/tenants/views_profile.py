"""
Tenant-Specific User Profile Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
import logging

from .models import TenantMember
from .serializers import TenantMemberSerializer
from apps.core.responses import success_response, error_response
from apps.authentication.serializers import UserSerializer

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Profile'],
    summary='Get current user tenant profile',
    description='Get current user\'s profile including tenant-specific role and information',
    responses={
        200: {
            'description': 'User profile with tenant-specific information',
            'content': {
                'application/json': {
                    'example': {
                        'success': True,
                        'data': {
                            'user': {
                                'id': 'uuid',
                                'email': 'user@example.com',
                                'first_name': 'John',
                                'last_name': 'Doe',
                                'full_name': 'John Doe',
                                'phone': '+1234567890',
                                'avatar_url': '',
                                'is_active': True,
                                'is_verified': True,
                            },
                            'tenant_membership': {
                                'id': 'uuid',
                                'role': 'admin',
                                'employee_id': 'ADM0001',
                                'department': 'Engineering',
                                'job_title': 'Senior Engineer',
                                'is_active': True,
                                'joined_at': '2025-01-01T00:00:00Z'
                            },
                            'tenant': {
                                'id': 'uuid',
                                'name': 'Acme Corp',
                                'slug': 'acme-corp'
                            }
                        }
                    }
                }
            }
        },
        403: {'description': 'Not a member of current tenant'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_profile(request):
    """
    Get current user's profile with tenant-specific information.
    
    This endpoint returns:
    - User basic information
    - Tenant membership (role, employee_id, department, job_title)
    - Current tenant information
    """
    try:
        # Check if user has tenant membership
        if not hasattr(request, 'tenant_membership') or not request.tenant_membership:
            return error_response(
                message='You are not a member of this organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        membership = request.tenant_membership
        
        data = {
            'user': UserSerializer(request.user).data,
            'tenant_membership': {
                'id': str(membership.id),
                'role': membership.role,
                'employee_id': membership.employee_id,
                'department': membership.department,
                'job_title': membership.job_title,
                'phone': membership.phone,
                'is_active': membership.is_active,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                # Helper flags
                'is_owner': membership.is_owner,
                'is_admin': membership.is_admin,
                'is_manager': membership.is_manager,
                'is_technician': membership.is_technician,
                'is_customer': membership.is_customer,
            },
            'tenant': {
                'id': str(membership.tenant.id),
                'name': membership.tenant.name,
                'slug': membership.tenant.slug,
            }
        }
        
        return success_response(
            data=data,
            message='Profile retrieved successfully'
        )
        
    except Exception as e:
        logger.error(f"Failed to get user profile: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve profile',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Profile'],
    summary='Get all user tenant memberships',
    description='Get list of all tenants the current user is a member of',
    responses={
        200: {
            'description': 'List of tenant memberships',
        },
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_tenant_memberships(request):
    """
    Get all tenant memberships for the current user.
    
    This is useful for:
    - Tenant switcher in UI
    - Showing user which organizations they belong to
    - Displaying different roles across tenants
    """
    try:
        memberships = TenantMember.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('tenant')
        
        data = []
        for membership in memberships:
            data.append({
                'id': str(membership.id),
                'tenant': {
                    'id': str(membership.tenant.id),
                    'name': membership.tenant.name,
                    'slug': membership.tenant.slug,
                },
                'role': membership.role,
                'employee_id': membership.employee_id,
                'department': membership.department,
                'job_title': membership.job_title,
                'phone': membership.phone,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
            })
        
        return success_response(
            data=data,
            message=f'Found {len(data)} tenant memberships'
        )
        
    except Exception as e:
        logger.error(f"Failed to get tenant memberships: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve tenant memberships',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Profile'],
    summary='Update tenant-specific profile',
    description='Update current user\'s tenant-specific information (department, job_title)',
    request={
        'application/json': {
            'example': {
                'department': 'Engineering',
                'job_title': 'Senior Engineer'
            }
        }
    },
    responses={
        200: {'description': 'Profile updated successfully'},
        403: {'description': 'Not a member of current tenant'},
    }
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_tenant_profile(request):
    """
    Update current user's tenant-specific profile information.
    
    Users can update their own:
    - department
    - job_title
    
    Note: role and employee_id can only be changed by admins/owners.
    """
    try:
        # Check if user has tenant membership
        if not hasattr(request, 'tenant_membership') or not request.tenant_membership:
            return error_response(
                message='You are not a member of this organization',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        membership = request.tenant_membership
        
        # Allow users to update their own department, job_title, and phone
        allowed_fields = ['department', 'job_title', 'phone']
        
        updated = False
        for field in allowed_fields:
            if field in request.data:
                setattr(membership, field, request.data[field])
                updated = True
        
        if updated:
            membership.save()
            logger.info(f"User {request.user.email} updated their tenant profile")
        
        data = {
            'id': str(membership.id),
            'role': membership.role,
            'employee_id': membership.employee_id,
            'department': membership.department,
            'job_title': membership.job_title,
            'phone': membership.phone,
        }
        
        return success_response(
            data=data,
            message='Profile updated successfully'
        )
        
    except Exception as e:
        logger.error(f"Failed to update profile: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to update profile',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
