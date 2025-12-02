"""
Tenant/Onboarding Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiExample
import logging

from .models import Tenant, TenantMember, TenantSettings
from .serializers import (
    TenantSerializer, CreateTenantSerializer, UpdateTenantSerializer,
    TenantMemberSerializer, InviteMemberSerializer, TenantSettingsSerializer,
    OnboardingStepSerializer
)
from apps.core.responses import success_response, error_response
from apps.authentication.models import User
from functools import wraps

logger = logging.getLogger(__name__)


def public_schema_only(view_func):
    """
    Decorator to restrict view access to public schema only.
    Used for onboarding endpoints that should only be accessible from localhost.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.db import connection
        
        current_schema = connection.schema_name
        if current_schema != 'public':
            return error_response(
                message="This endpoint is only available from the onboarding portal. Please access via http://localhost:8000",
                status_code=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


@extend_schema(
    tags=['Onboarding'],
    summary='Create company/tenant',
    description='Create a new company/tenant and add the current user as owner',
    request=CreateTenantSerializer,
    responses={
        201: TenantSerializer,
        400: {'description': 'Invalid company data'},
    },
    examples=[
        OpenApiExample(
            'Create Company',
            value={
                'name': 'Acme Corporation',
                'company_email': 'contact@acme.com',
                'company_phone': '+1234567890',
                'company_size': '11-50',
                'industry': 'Manufacturing',
                'city': 'New York',
                'state': 'NY',
                'country': 'USA'
            },
            request_only=True
        )
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def create_tenant(request):
    """
    Create a new tenant/company and add current user as owner.
    
    Note: This endpoint is only accessible from the public schema (localhost).
    Accessing from a tenant subdomain will return 403 Forbidden.
    """
    from django.db import connection
    
    serializer = CreateTenantSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid company data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant creation
            connection.set_schema_to_public()
            
            # Create tenant
            tenant = serializer.save()
            
            # Start trial (default 15 days, can be customized)
            trial_days = request.data.get('trial_days', 15)
            tenant.start_trial(days=trial_days)
            
            # Create tenant settings
            TenantSettings.objects.create(tenant=tenant)
            
            # Add current user as owner
            TenantMember.objects.create(
                tenant=tenant,
                user=request.user,
                role='owner'
            )
            
            # Automatically create domain for the tenant
            from apps.tenants.models import Domain
            domain_name = f"{tenant.slug}.localhost"
            Domain.objects.create(
                domain=domain_name,
                tenant=tenant,
                is_primary=True
            )
            
            logger.info(f"Tenant created: {tenant.name} by {request.user.email}")
            logger.info(f"Domain created: {domain_name} -> {tenant.schema_name}")
            
            return success_response(
                data={
                    **TenantSerializer(tenant).data,
                    'domain': domain_name,
                    'access_url': f"http://{domain_name}:8000"
                },
                message="Company created successfully",
                status_code=status.HTTP_201_CREATED
            )
            
    except Exception as e:
        logger.error(f"Failed to create tenant: {str(e)}", exc_info=True)
        return error_response(
            message="Failed to create company. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Get current tenant',
    description='Get current user\'s tenant/company information',
    responses={
        200: TenantSerializer,
        404: {'description': 'No tenant found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def current_tenant(request):
    """
    Get current user's tenant.
    
    Note: Only accessible from public schema (localhost).
    """
    try:
        membership = request.user.tenant_memberships.filter(is_active=True).first()
        
        if not membership:
            return success_response(
                data=None,
                message="No company found for this user"
            )
        
        tenant = membership.tenant
        serializer = TenantSerializer(tenant)
        
        return success_response(
            data=serializer.data,
            message="Tenant retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get current tenant: {str(e)}")
        return error_response(
            message="Failed to retrieve company information",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Update tenant',
    description='Update tenant/company information (Owner/Admin only)',
    request=UpdateTenantSerializer,
    responses={
        200: TenantSerializer,
        403: {'description': 'Permission denied'},
        404: {'description': 'Tenant not found'},
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@public_schema_only
def update_tenant(request):
    """
    Update tenant information.
    
    Note: Only accessible from public schema (localhost).
    Tenant updates must happen in the public schema.
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant updates
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can update company information",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            tenant = membership.tenant
            serializer = UpdateTenantSerializer(tenant, data=request.data, partial=True)
            
            if not serializer.is_valid():
                return error_response(
                    message="Invalid company data",
                    details=serializer.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save()
            
            return success_response(
                data=TenantSerializer(tenant).data,
                message="Company updated successfully"
            )
        
    except Exception as e:
        logger.error(f"Failed to update tenant: {str(e)}")
        return error_response(
            message="Failed to update company",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Complete onboarding step',
    description='Mark an onboarding step as complete and move to next step',
    request=OnboardingStepSerializer,
    responses={
        200: TenantSerializer,
        400: {'description': 'Invalid step data'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def complete_onboarding_step(request):
    """
    Complete an onboarding step.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    serializer = OnboardingStepSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid step data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant updates
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            tenant = membership.tenant
            step = serializer.validated_data['step']
            
            # Update onboarding step
            if step > tenant.onboarding_step:
                tenant.onboarding_step = step
            
            # Mark onboarding as completed if on final step
            if step >= 5:
                tenant.onboarding_completed = True
            
            tenant.save()
            
            return success_response(
                data=TenantSerializer(tenant).data,
                message=f"Onboarding step {step} completed"
            )
        
    except Exception as e:
        logger.error(f"Failed to complete onboarding step: {str(e)}")
        return error_response(
            message="Failed to complete onboarding step",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Get tenant members',
    description='Get list of all members in the tenant',
    responses={
        200: TenantMemberSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def tenant_members(request):
    """
    Get tenant members.
    
    Note: Only accessible from public schema (localhost).
    """
    try:
        membership = request.user.tenant_memberships.filter(is_active=True).first()
        
        if not membership:
            return error_response(
                message="No company found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        members = membership.tenant.members.filter(is_active=True)
        serializer = TenantMemberSerializer(members, many=True)
        
        return success_response(
            data=serializer.data,
            message="Members retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get tenant members: {str(e)}")
        return error_response(
            message="Failed to retrieve members",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Invite member',
    description='Invite a new member to the tenant (Owner/Admin only)',
    request=InviteMemberSerializer,
    responses={
        200: {'description': 'Invitation sent successfully'},
        403: {'description': 'Permission denied'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def invite_member(request):
    """
    Invite a member to tenant.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    serializer = InviteMemberSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid invitation data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant member operations
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
        
        if not membership:
            return error_response(
                message="No company found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        if membership.role not in ['owner', 'admin', 'manager']:
            return error_response(
                message="Only owners, admins, and managers can invite members",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        email = serializer.validated_data['email']
        role = serializer.validated_data['role']
        
        # Check if user already exists
        try:
            user = User.objects.get(email=email)
            
            # Check if already an active member
            existing_member = membership.tenant.members.filter(user=user).first()
            
            if existing_member:
                if existing_member.is_active:
                    return error_response(
                        message="User is already a member of this company",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # User was previously a member but was removed - reactivate directly (no invitation needed)
                    existing_member.is_active = True
                    existing_member.role = role
                    existing_member.save()
                    logger.info(f"Reactivated member: {email} in {membership.tenant.name}")
                    message = f"User {email} has been reactivated and added back to the company"
            else:
                # User exists but was never a member - send invitation (requires acceptance)
                from apps.tenants.models import TenantInvitation
                import secrets
                from datetime import timedelta
                
                # Check if invitation already exists (any status)
                existing_invitation = TenantInvitation.objects.filter(
                    tenant=membership.tenant,
                    email=email
                ).first()
                
                if existing_invitation:
                    if existing_invitation.status == 'pending' and existing_invitation.is_valid():
                        return error_response(
                            message=f"An invitation has already been sent to {email}",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        # Reuse existing invitation (expired, revoked, or accepted)
                        existing_invitation.status = 'pending'
                        existing_invitation.role = role
                        existing_invitation.invited_by = request.user
                        existing_invitation.token = secrets.token_urlsafe(32)
                        existing_invitation.expires_at = timezone.now() + timedelta(days=7)
                        existing_invitation.accepted_at = None
                        existing_invitation.save()
                        invitation = existing_invitation
                else:
                    # Create new invitation
                    invitation = TenantInvitation.objects.create(
                        tenant=membership.tenant,
                        email=email,
                        role=role,
                        invited_by=request.user,
                        token=secrets.token_urlsafe(32),
                        expires_at=timezone.now() + timedelta(days=7)
                    )
                
                # Send invitation email
                try:
                    from apps.core.email_utils import send_team_invitation_email
                    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                    send_team_invitation_email(invitation, frontend_url)
                    logger.info(f"Invitation email sent to existing user {email} to join {membership.tenant.name}")
                except Exception as e:
                    logger.error(f"Failed to send invitation email to {email}: {str(e)}")
                    # Don't fail the invitation creation if email fails
                
                message = f"Invitation sent to {email}. They need to accept the invitation to join."
            
        except User.DoesNotExist:
            # Create invitation for non-existent user
            from apps.tenants.models import TenantInvitation
            import secrets
            from datetime import timedelta
            
            # Check if invitation already exists (any status)
            existing_invitation = TenantInvitation.objects.filter(
                tenant=membership.tenant,
                email=email
            ).first()
            
            if existing_invitation:
                if existing_invitation.status == 'pending' and existing_invitation.is_valid():
                    return error_response(
                        message=f"An invitation has already been sent to {email}",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    # Reuse existing invitation (expired, revoked, declined, or accepted)
                    existing_invitation.status = 'pending'
                    existing_invitation.role = role
                    existing_invitation.invited_by = request.user
                    existing_invitation.token = secrets.token_urlsafe(32)
                    existing_invitation.expires_at = timezone.now() + timedelta(days=7)
                    existing_invitation.accepted_at = None
                    existing_invitation.save()
                    invitation = existing_invitation
            else:
                # Create new invitation
                invitation = TenantInvitation.objects.create(
                    tenant=membership.tenant,
                    email=email,
                    role=role,
                    invited_by=request.user,
                    token=secrets.token_urlsafe(32),
                    expires_at=timezone.now() + timedelta(days=7)
                )
            
            # Send invitation email
            try:
                from apps.core.email_utils import send_team_invitation_email
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                send_team_invitation_email(invitation, frontend_url)
                logger.info(f"Invitation email sent to {email} to join {membership.tenant.name}")
            except Exception as e:
                logger.error(f"Failed to send invitation email to {email}: {str(e)}")
                # Don't fail the invitation creation if email fails
            
            message = f"Invitation sent to {email}. They need to register with this email to join."
        
        return success_response(
            message=message
        )
        
    except Exception as e:
        logger.error(f"Failed to invite member: {str(e)}")
        return error_response(
            message="Failed to send invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@extend_schema(
    tags=['Onboarding'],
    summary='Get pending invitations',
    description='Get list of pending invitations for the tenant (Owner/Admin only)',
    responses={
        200: {'description': 'List of pending invitations'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def pending_invitations(request):
    """
    Get pending invitations for the tenant.
    
    Note: Only accessible from public schema (localhost).
    """
    try:
        membership = request.user.tenant_memberships.filter(is_active=True).first()
        
        if not membership:
            return error_response(
                message="No company found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        if membership.role not in ['owner', 'admin', 'manager']:
            return error_response(
                message="Only owners, admins, and managers can view invitations",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        from apps.tenants.models import TenantInvitation
        
        invitations = TenantInvitation.objects.filter(
            tenant=membership.tenant,
            status='pending'
        ).order_by('-created_at')
        
        data = []
        for inv in invitations:
            data.append({
                'id': str(inv.id),
                'email': inv.email,
                'role': inv.role,
                'invited_by': inv.invited_by.email if inv.invited_by else None,
                'created_at': inv.created_at.isoformat(),
                'expires_at': inv.expires_at.isoformat(),
                'is_valid': inv.is_valid()
            })
        
        return success_response(
            data=data,
            message=f"Found {len(data)} pending invitations"
        )
        
    except Exception as e:
        logger.error(f"Failed to get pending invitations: {str(e)}")
        return error_response(
            message="Failed to retrieve invitations",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Check invitation by email',
    description='Check if there is a pending invitation for the current user\'s email',
    responses={
        200: {'description': 'Invitation details if found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def check_invitation(request):
    """
    Check if user has any pending invitations.
    
    Note: Only accessible from public schema (localhost).
    """
    try:
        from apps.tenants.models import TenantInvitation
        
        invitations = TenantInvitation.objects.filter(
            email=request.user.email,
            status='pending'
        ).order_by('-created_at')
        
        data = []
        for inv in invitations:
            if inv.is_valid():
                data.append({
                    'id': str(inv.id),
                    'tenant_name': inv.tenant.name,
                    'role': inv.role,
                    'invited_by': inv.invited_by.email if inv.invited_by else None,
                    'created_at': inv.created_at.isoformat(),
                    'expires_at': inv.expires_at.isoformat()
                })
        
        return success_response(
            data=data,
            message=f"Found {len(data)} pending invitations"
        )
        
    except Exception as e:
        logger.error(f"Failed to check invitations: {str(e)}")
        return error_response(
            message="Failed to check invitations",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Get invitation details by token (Public)',
    description='Get invitation details using the invitation token - No authentication required',
    responses={
        200: {'description': 'Invitation details'},
        404: {'description': 'Invitation not found or expired'},
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
@public_schema_only
def get_invitation_by_token(request, token):
    """
    Get invitation details by token (public endpoint).
    
    Note: Only accessible from public schema (localhost).
    """
    try:
        from apps.tenants.models import TenantInvitation
        
        invitation = TenantInvitation.objects.get(
            token=token,
            status='pending'
        )
        
        if not invitation.is_valid():
            return error_response(
                message="This invitation has expired",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        return success_response(
            data={
                'id': str(invitation.id),
                'email': invitation.email,
                'tenant_name': invitation.tenant.name,
                'role': invitation.role,
                'invited_by': invitation.invited_by.email if invitation.invited_by else None,
                'expires_at': invitation.expires_at.isoformat(),
            },
            message="Invitation details retrieved successfully"
        )
        
    except TenantInvitation.DoesNotExist:
        return error_response(
            message="Invitation not found or invalid token",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to get invitation: {str(e)}")
        return error_response(
            message="Failed to retrieve invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Accept invitation by token',
    description='Accept a pending invitation to join a tenant using invitation token',
    responses={
        200: {'description': 'Invitation accepted successfully'},
        404: {'description': 'Invitation not found or expired'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def accept_invitation_by_token(request, token):
    """
    Accept an invitation to join a tenant using the invitation token.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant operations
            connection.set_schema_to_public()
            
            from apps.tenants.models import TenantInvitation
            
            invitation = TenantInvitation.objects.get(
                token=token,
                email=request.user.email,
                status='pending'
            )
            
            if not invitation.is_valid():
                return error_response(
                    message="This invitation has expired",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user is already a member
            if invitation.tenant.members.filter(user=request.user).exists():
                invitation.status = 'accepted'
                invitation.accepted_at = timezone.now()
                invitation.save()
                
                return error_response(
                    message="You are already a member of this company",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Accept invitation (creates membership)
            invitation.accept(request.user)
            
            return success_response(
                data={
                    'tenant_name': invitation.tenant.name,
                    'role': invitation.role
                },
                message=f"Successfully joined {invitation.tenant.name}"
            )
        
    except TenantInvitation.DoesNotExist:
        return error_response(
            message="Invitation not found or invalid token",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to accept invitation: {str(e)}")
        return error_response(
            message="Failed to accept invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Keep old function for backward compatibility (deprecated)
@extend_schema(
    tags=['Onboarding'],
    summary='Accept invitation (deprecated)',
    description='Accept a pending invitation to join a tenant - Use accept_invitation_by_token instead',
    responses={
        200: {'description': 'Invitation accepted successfully'},
        404: {'description': 'Invitation not found or expired'},
    },
    deprecated=True
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def accept_invitation(request, invitation_id):
    """
    Accept an invitation to join a tenant.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema for tenant operations
            connection.set_schema_to_public()
            
            from apps.tenants.models import TenantInvitation
            
            invitation = TenantInvitation.objects.get(
                id=invitation_id,
                email=request.user.email,
                status='pending'
            )
            
            if not invitation.is_valid():
                return error_response(
                    message="This invitation has expired",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user is already a member
            if invitation.tenant.members.filter(user=request.user).exists():
                invitation.status = 'accepted'
                invitation.accepted_at = timezone.now()
                invitation.save()
                
                return error_response(
                    message="You are already a member of this company",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Accept invitation (creates membership)
            invitation.accept(request.user)
            
            return success_response(
                data={
                    'tenant_name': invitation.tenant.name,
                    'role': invitation.role
                },
                message=f"Successfully joined {invitation.tenant.name}"
            )
        
    except TenantInvitation.DoesNotExist:
        return error_response(
            message="Invitation not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to accept invitation: {str(e)}")
        return error_response(
            message="Failed to accept invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Update member role',
    description='Update a team member\'s role (Owner/Admin only)',
    responses={
        200: TenantMemberSerializer,
        403: {'description': 'Permission denied'},
        404: {'description': 'Member not found'},
    }
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@public_schema_only
def update_member_role(request, member_id):
    """
    Update a team member's role.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Only owners, admins, and managers can update roles
            if membership.role not in ['owner', 'admin', 'manager']:
                return error_response(
                    message="Only owners, admins, and managers can update member roles",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Get the member to update
            member = TenantMember.objects.get(
                id=member_id,
                tenant=membership.tenant
            )
            
            # Prevent changing owner role (only one owner allowed)
            if member.role == 'owner':
                return error_response(
                    message="Cannot change the owner's role",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Prevent non-owners from creating new owners
            new_role = request.data.get('role')
            if new_role == 'owner' and membership.role != 'owner':
                return error_response(
                    message="Only the owner can assign the owner role",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Update role
            member.role = new_role
            member.save()
            
            logger.info(f"Member role updated: {member.user.email} -> {new_role} by {request.user.email}")
            
            return success_response(
                data=TenantMemberSerializer(member).data,
                message=f"Member role updated to {new_role}"
            )
        
    except TenantMember.DoesNotExist:
        return error_response(
            message="Member not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to update member role: {str(e)}")
        return error_response(
            message="Failed to update member role",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Remove member',
    description='Remove a team member from the tenant (Owner/Admin only)',
    responses={
        200: {'description': 'Member removed successfully'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Member not found'},
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@public_schema_only
def remove_member(request, member_id):
    """
    Remove a team member from the tenant.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Only owners, admins, and managers can remove members
            if membership.role not in ['owner', 'admin', 'manager']:
                return error_response(
                    message="Only owners, admins, and managers can remove members",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Get the member to remove
            member = TenantMember.objects.get(
                id=member_id,
                tenant=membership.tenant
            )
            
            # Prevent removing the owner
            if member.role == 'owner':
                return error_response(
                    message="Cannot remove the owner",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Prevent removing yourself
            if member.user.id == request.user.id:
                return error_response(
                    message="You cannot remove yourself. Please contact the owner.",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            # Soft delete (deactivate) instead of hard delete
            member.is_active = False
            member.save()
            
            logger.info(f"Member removed: {member.user.email} from {membership.tenant.name} by {request.user.email}")
            
            return success_response(
                message=f"Member {member.user.email} removed successfully"
            )
        
    except TenantMember.DoesNotExist:
        return error_response(
            message="Member not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to remove member: {str(e)}")
        return error_response(
            message="Failed to remove member",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Resend invitation',
    description='Resend an invitation email (Owner/Admin only)',
    responses={
        200: {'description': 'Invitation resent successfully'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Invitation not found'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def resend_invitation(request, invitation_id):
    """
    Resend an invitation.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Only owners, admins, and managers can resend invitations
            if membership.role not in ['owner', 'admin', 'manager']:
                return error_response(
                    message="Only owners, admins, and managers can resend invitations",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            from apps.tenants.models import TenantInvitation
            from datetime import timedelta
            
            # Get the invitation
            invitation = TenantInvitation.objects.get(
                id=invitation_id,
                tenant=membership.tenant
            )
            
            # Update expiration date
            invitation.expires_at = timezone.now() + timedelta(days=7)
            invitation.status = 'pending'
            invitation.save()
            
            # Send invitation email
            try:
                from apps.core.email_utils import send_team_invitation_email
                frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
                send_team_invitation_email(invitation, frontend_url)
                logger.info(f"Invitation email resent to {invitation.email} by {request.user.email}")
            except Exception as e:
                logger.error(f"Failed to resend invitation email to {invitation.email}: {str(e)}")
                # Don't fail if email fails
            
            return success_response(
                message=f"Invitation resent to {invitation.email}"
            )
        
    except TenantInvitation.DoesNotExist:
        return error_response(
            message="Invitation not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to resend invitation: {str(e)}")
        return error_response(
            message="Failed to resend invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Revoke invitation',
    description='Revoke/cancel a pending invitation (Owner/Admin only)',
    responses={
        200: {'description': 'Invitation revoked successfully'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Invitation not found'},
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@public_schema_only
def revoke_invitation(request, invitation_id):
    """
    Revoke a pending invitation.
    
    Note: Only accessible from public schema (localhost).
    """
    from django.db import connection
    
    try:
        with transaction.atomic():
            # Switch to public schema
            connection.set_schema_to_public()
            
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Only owners, admins, and managers can revoke invitations
            if membership.role not in ['owner', 'admin', 'manager']:
                return error_response(
                    message="Only owners, admins, and managers can revoke invitations",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            from apps.tenants.models import TenantInvitation
            
            # Get the invitation
            invitation = TenantInvitation.objects.get(
                id=invitation_id,
                tenant=membership.tenant
            )
            
            # Update status to revoked
            invitation.status = 'revoked'
            invitation.save()
            
            logger.info(f"Invitation revoked: {invitation.email} by {request.user.email}")
            
            return success_response(
                message=f"Invitation to {invitation.email} has been revoked"
            )
        
    except TenantInvitation.DoesNotExist:
        return error_response(
            message="Invitation not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to revoke invitation: {str(e)}")
        return error_response(
            message="Failed to revoke invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@extend_schema(
    tags=['Onboarding'],
    summary='Get or update tenant settings',
    description='Get or update tenant settings including wage and working hours configuration',
    request=TenantSettingsSerializer,
    responses={
        200: TenantSettingsSerializer,
        403: {'description': 'Permission denied'},
        404: {'description': 'Settings not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def tenant_settings(request):
    """
    Get or update tenant settings.
    Works in both public and tenant schemas.
    """
    try:
        from django.db import connection
        
        # Get current tenant and check permissions
        if connection.schema_name == 'public':
            # In public schema, get from user's membership
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Check permissions for PUT/PATCH
            if request.method in ['PUT', 'PATCH']:
                if membership.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can update settings",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            
            # Switch to tenant schema to get settings
            connection.set_tenant(membership.tenant)
        else:
            # In tenant schema, check role from TenantMember
            if request.method in ['PUT', 'PATCH']:
                try:
                    member = TenantMember.objects.get(user=request.user, is_active=True)
                    if member.role not in ['owner', 'admin']:
                        return error_response(
                            message="Only owners and admins can update settings",
                            status_code=status.HTTP_403_FORBIDDEN
                        )
                except TenantMember.DoesNotExist:
                    return error_response(
                        message="You are not a member of this company",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
        
        # Get or create tenant settings
        settings, created = TenantSettings.objects.get_or_create(
            tenant_id=connection.tenant.id if hasattr(connection, 'tenant') else None
        )
        
        # Handle GET request
        if request.method == 'GET':
            serializer = TenantSettingsSerializer(settings)
            return success_response(
                data=serializer.data,
                message="Settings retrieved successfully"
            )
        
        # Handle PUT/PATCH request
        serializer = TenantSettingsSerializer(settings, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid settings data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        logger.info(f"Tenant settings updated by {request.user.email}")
        
        return success_response(
            data=serializer.data,
            message="Settings updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to process tenant settings: {str(e)}")
        return error_response(
            message="Failed to process settings",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# ============================================================================
# Technician Wage Rates (Phase 2)
# ============================================================================

@extend_schema(
    tags=['Onboarding'],
    summary='Get all technician wage rates',
    description='Get list of all technician wage rates for the current tenant',
    responses={
        200: {'description': 'List of technician wage rates'},
        403: {'description': 'Permission denied'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_technician_wage_rates(request):
    """
    Get all technician wage rates for the current tenant.
    Only accessible by Owner/Admin.
    """
    try:
        from django.db import connection
        from apps.tenants.models import TechnicianWageRate
        from apps.tenants.serializers import TechnicianWageRateSerializer
        
        # Check permissions
        if connection.schema_name == 'public':
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can view wage rates",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            connection.set_tenant(membership.tenant)
        else:
            try:
                member = TenantMember.objects.get(user=request.user, is_active=True)
                if member.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can view wage rates",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except TenantMember.DoesNotExist:
                return error_response(
                    message="You are not a member of this company",
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # Get all wage rates
        rates = TechnicianWageRate.objects.select_related(
            'technician', 'created_by'
        ).order_by('-effective_from', '-created_at')
        
        serializer = TechnicianWageRateSerializer(rates, many=True)
        
        return success_response(
            data=serializer.data,
            message="Wage rates retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get technician wage rates: {str(e)}")
        return error_response(
            message="Failed to retrieve wage rates",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Create technician wage rate',
    description='Create a new wage rate for a technician (Owner/Admin only)',
    request={'application/json': {
        'type': 'object',
        'properties': {
            'technician': {'type': 'string', 'format': 'uuid'},
            'normal_hourly_rate': {'type': 'number'},
            'overtime_hourly_rate': {'type': 'number'},
            'effective_from': {'type': 'string', 'format': 'date'},
            'effective_to': {'type': 'string', 'format': 'date', 'nullable': True},
            'notes': {'type': 'string'},
        },
        'required': ['technician', 'normal_hourly_rate', 'overtime_hourly_rate', 'effective_from']
    }},
    responses={
        201: {'description': 'Wage rate created successfully'},
        400: {'description': 'Invalid data'},
        403: {'description': 'Permission denied'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_technician_wage_rate(request):
    """
    Create a new technician wage rate.
    Only accessible by Owner/Admin.
    """
    try:
        from django.db import connection
        from apps.tenants.models import TechnicianWageRate
        from apps.tenants.serializers import CreateTechnicianWageRateSerializer
        
        # Check permissions
        if connection.schema_name == 'public':
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can create wage rates",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            connection.set_tenant(membership.tenant)
        else:
            try:
                member = TenantMember.objects.get(user=request.user, is_active=True)
                if member.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can create wage rates",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except TenantMember.DoesNotExist:
                return error_response(
                    message="You are not a member of this company",
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # Validate and create
        serializer = CreateTechnicianWageRateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid wage rate data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Set created_by
        rate = serializer.save(created_by=request.user)
        
        logger.info(f"Wage rate created for technician {rate.technician.email} by {request.user.email}")
        
        from apps.tenants.serializers import TechnicianWageRateSerializer
        return success_response(
            data=TechnicianWageRateSerializer(rate).data,
            message="Wage rate created successfully",
            status_code=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"Failed to create technician wage rate: {str(e)}")
        return error_response(
            message="Failed to create wage rate",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Get technician wage rate by ID',
    description='Get a specific technician wage rate',
    responses={
        200: {'description': 'Wage rate details'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Wage rate not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_technician_wage_rate(request, rate_id):
    """
    Get a specific technician wage rate.
    Only accessible by Owner/Admin.
    """
    try:
        from django.db import connection
        from apps.tenants.models import TechnicianWageRate
        from apps.tenants.serializers import TechnicianWageRateSerializer
        
        # Check permissions
        if connection.schema_name == 'public':
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can view wage rates",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            connection.set_tenant(membership.tenant)
        else:
            try:
                member = TenantMember.objects.get(user=request.user, is_active=True)
                if member.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can view wage rates",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except TenantMember.DoesNotExist:
                return error_response(
                    message="You are not a member of this company",
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # Get wage rate
        rate = TechnicianWageRate.objects.select_related(
            'technician', 'created_by'
        ).get(id=rate_id)
        
        serializer = TechnicianWageRateSerializer(rate)
        
        return success_response(
            data=serializer.data,
            message="Wage rate retrieved successfully"
        )
        
    except TechnicianWageRate.DoesNotExist:
        return error_response(
            message="Wage rate not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to get technician wage rate: {str(e)}")
        return error_response(
            message="Failed to retrieve wage rate",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Update technician wage rate',
    description='Update an existing technician wage rate (Owner/Admin only)',
    request={'application/json': {
        'type': 'object',
        'properties': {
            'normal_hourly_rate': {'type': 'number'},
            'overtime_hourly_rate': {'type': 'number'},
            'effective_from': {'type': 'string', 'format': 'date'},
            'effective_to': {'type': 'string', 'format': 'date', 'nullable': True},
            'notes': {'type': 'string'},
            'is_active': {'type': 'boolean'},
        }
    }},
    responses={
        200: {'description': 'Wage rate updated successfully'},
        400: {'description': 'Invalid data'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Wage rate not found'},
    }
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_technician_wage_rate(request, rate_id):
    """
    Update a technician wage rate.
    Only accessible by Owner/Admin.
    """
    try:
        from django.db import connection
        from apps.tenants.models import TechnicianWageRate
        from apps.tenants.serializers import TechnicianWageRateSerializer
        
        # Check permissions
        if connection.schema_name == 'public':
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can update wage rates",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            connection.set_tenant(membership.tenant)
        else:
            try:
                member = TenantMember.objects.get(user=request.user, is_active=True)
                if member.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can update wage rates",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except TenantMember.DoesNotExist:
                return error_response(
                    message="You are not a member of this company",
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # Get and update wage rate
        rate = TechnicianWageRate.objects.get(id=rate_id)
        
        serializer = TechnicianWageRateSerializer(rate, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid wage rate data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        logger.info(f"Wage rate updated for technician {rate.technician.email} by {request.user.email}")
        
        return success_response(
            data=serializer.data,
            message="Wage rate updated successfully"
        )
        
    except TechnicianWageRate.DoesNotExist:
        return error_response(
            message="Wage rate not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to update technician wage rate: {str(e)}")
        return error_response(
            message="Failed to update wage rate",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Onboarding'],
    summary='Delete technician wage rate',
    description='Delete a technician wage rate (Owner/Admin only)',
    responses={
        200: {'description': 'Wage rate deleted successfully'},
        403: {'description': 'Permission denied'},
        404: {'description': 'Wage rate not found'},
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_technician_wage_rate(request, rate_id):
    """
    Delete a technician wage rate.
    Only accessible by Owner/Admin.
    """
    try:
        from django.db import connection
        from apps.tenants.models import TechnicianWageRate
        
        # Check permissions
        if connection.schema_name == 'public':
            membership = request.user.tenant_memberships.filter(is_active=True).first()
            if not membership:
                return error_response(
                    message="No company found",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            if membership.role not in ['owner', 'admin']:
                return error_response(
                    message="Only owners and admins can delete wage rates",
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            connection.set_tenant(membership.tenant)
        else:
            try:
                member = TenantMember.objects.get(user=request.user, is_active=True)
                if member.role not in ['owner', 'admin']:
                    return error_response(
                        message="Only owners and admins can delete wage rates",
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except TenantMember.DoesNotExist:
                return error_response(
                    message="You are not a member of this company",
                    status_code=status.HTTP_403_FORBIDDEN
                )
        
        # Get and delete wage rate
        rate = TechnicianWageRate.objects.get(id=rate_id)
        technician_email = rate.technician.email
        rate.delete()
        
        logger.info(f"Wage rate deleted for technician {technician_email} by {request.user.email}")
        
        return success_response(
            message="Wage rate deleted successfully"
        )
        
    except TechnicianWageRate.DoesNotExist:
        return error_response(
            message="Wage rate not found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to delete technician wage rate: {str(e)}")
        return error_response(
            message="Failed to delete wage rate",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
