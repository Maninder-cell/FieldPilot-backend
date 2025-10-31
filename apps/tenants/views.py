"""
Tenant/Onboarding Views

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
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

logger = logging.getLogger(__name__)


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
def create_tenant(request):
    """
    Create a new tenant/company and add current user as owner.
    """
    serializer = CreateTenantSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid company data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create tenant
            tenant = serializer.save()
            
            # Start 14-day trial
            tenant.start_trial(days=14)
            
            # Create tenant settings
            TenantSettings.objects.create(tenant=tenant)
            
            # Add current user as owner
            TenantMember.objects.create(
                tenant=tenant,
                user=request.user,
                role='owner'
            )
            
            logger.info(f"Tenant created: {tenant.name} by {request.user.email}")
            
            return success_response(
                data=TenantSerializer(tenant).data,
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
def current_tenant(request):
    """
    Get current user's tenant.
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
def update_tenant(request):
    """
    Update tenant information.
    """
    try:
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
def complete_onboarding_step(request):
    """
    Complete an onboarding step.
    """
    serializer = OnboardingStepSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid step data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
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
def tenant_members(request):
    """
    Get tenant members.
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
def invite_member(request):
    """
    Invite a member to tenant.
    """
    serializer = InviteMemberSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid invitation data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        membership = request.user.tenant_memberships.filter(is_active=True).first()
        
        if not membership:
            return error_response(
                message="No company found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        if membership.role not in ['owner', 'admin']:
            return error_response(
                message="Only owners and admins can invite members",
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        email = serializer.validated_data['email']
        role = serializer.validated_data['role']
        
        # Check if user already exists
        try:
            user = User.objects.get(email=email)
            
            # Check if already a member
            if membership.tenant.members.filter(user=user).exists():
                return error_response(
                    message="User is already a member of this company",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Add as member
            TenantMember.objects.create(
                tenant=membership.tenant,
                user=user,
                role=role
            )
            
            message = f"User {email} added to company"
            
        except User.DoesNotExist:
            # TODO: Send invitation email
            message = f"Invitation sent to {email}"
        
        return success_response(
            message=message
        )
        
    except Exception as e:
        logger.error(f"Failed to invite member: {str(e)}")
        return error_response(
            message="Failed to send invitation",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
