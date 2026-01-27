"""
Facilities Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
import logging

from .models import Customer, CustomerInvitation, Facility, Building, Location
from .emails import send_customer_invitation_email
from .serializers import (
    CustomerSerializer, CreateCustomerSerializer, UpdateCustomerSerializer,
    CustomerInvitationSerializer, InviteCustomerSerializer, AcceptInvitationSerializer,
    FacilitySerializer, CreateFacilitySerializer, UpdateFacilitySerializer, FacilityListSerializer,
    BuildingSerializer, CreateBuildingSerializer, UpdateBuildingSerializer, BuildingListSerializer,
    LocationSerializer, CreateLocationSerializer, UpdateLocationSerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import (
    IsAdminUser, IsAdminManagerOwner, MethodRolePermission, 
    ensure_tenant_role, method_role_permissions, with_customer_tenant_context
)
from apps.tenants.decorators import check_tenant_permission

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Customers'],
    summary='List and create customers',
    description='Get paginated list of customers with filtering and search, or create a new customer',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('status', str, description='Filter by status (active, inactive, pending)'),
        OpenApiParameter('search', str, description='Search by name, email, or company name'),
    ],
    request=CreateCustomerSerializer,
    responses={
        200: CustomerSerializer(many=True),
        201: CustomerSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee'],
    POST=['admin', 'manager', 'owner']
)
def customer_list_create(request):
    """
    List customers with pagination and filtering, or create a new customer.
    """
    
    if request.method == 'GET':
        # Get queryset
        queryset = Customer.objects.all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(company_name__icontains=search)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = CustomerSerializer(page, many=True)
            data = serializer.data
            
            # Enrich with invitation information
            customer_ids = [customer['id'] for customer in data]
            invitations = CustomerInvitation.objects.filter(
                customer_id__in=customer_ids
            ).order_by('-created_at')
            
            # Create a mapping of customer_id to invitation info (most recent invitation)
            invitation_map = {}
            for inv in invitations:
                customer_id_str = str(inv.customer_id)
                if customer_id_str not in invitation_map:
                    invitation_map[customer_id_str] = {
                        'id': str(inv.id),
                        'status': inv.status,
                        'invited_at': inv.created_at.isoformat(),
                        'invited_by': inv.invited_by.email if inv.invited_by else None,
                        'expires_at': inv.expires_at.isoformat(),
                        'accepted_at': inv.accepted_at.isoformat() if inv.accepted_at else None,
                        'is_valid': inv.is_valid() if inv.status == 'pending' else False
                    }
            
            # Add invitation info to each customer
            for customer_data in data:
                customer_id = customer_data['id']
                if customer_id in invitation_map:
                    customer_data['invitation'] = invitation_map[customer_id]
                else:
                    customer_data['invitation'] = None
            
            return paginator.get_paginated_response({
                'success': True,
                'data': data,
                'message': 'Customers retrieved successfully'
            })
        
        serializer = CustomerSerializer(queryset, many=True)
        data = serializer.data
        
        # Enrich with invitation information for non-paginated response
        customer_ids = [customer['id'] for customer in data]
        invitations = CustomerInvitation.objects.filter(
            customer_id__in=customer_ids
        ).order_by('-created_at')
        
        # Create a mapping of customer_id to invitation info (most recent invitation)
        invitation_map = {}
        for inv in invitations:
            customer_id_str = str(inv.customer_id)
            if customer_id_str not in invitation_map:
                invitation_map[customer_id_str] = {
                    'id': str(inv.id),
                    'status': inv.status,
                    'invited_at': inv.created_at.isoformat(),
                    'invited_by': inv.invited_by.email if inv.invited_by else None,
                    'expires_at': inv.expires_at.isoformat(),
                    'accepted_at': inv.accepted_at.isoformat() if inv.accepted_at else None,
                    'is_valid': inv.is_valid() if inv.status == 'pending' else False
                }
        
        # Add invitation info to each customer
        for customer_data in data:
            customer_id = customer_data['id']
            if customer_id in invitation_map:
                customer_data['invitation'] = invitation_map[customer_id]
            else:
                customer_data['invitation'] = None
        
        return success_response(
            data=data,
            message='Customers retrieved successfully'
        )
    
    elif request.method == 'POST':
        serializer = CreateCustomerSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid customer data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                customer = serializer.save(created_by=request.user)
                
                logger.info(f"Customer created: {customer.name} by {request.user.email}")
                
                return success_response(
                    data=CustomerSerializer(customer).data,
                    message='Customer created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create customer: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create customer',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Customers'],
    summary='Get, update, or delete customer',
    description='Retrieve customer details, update customer information, or soft delete a customer',
    request=UpdateCustomerSerializer,
    responses={
        200: CustomerSerializer,
        404: {'description': 'Customer not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee'],
    PUT=['admin', 'manager', 'owner'],
    PATCH=['admin', 'manager', 'owner'],
    DELETE=['admin', 'manager', 'owner']
)
def customer_detail(request, customer_id):
    """
    Retrieve, update, or delete a customer.
    """
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return error_response(
            message='Customer not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = CustomerSerializer(customer)
        return success_response(
            data=serializer.data,
            message='Customer retrieved successfully'
        )
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UpdateCustomerSerializer(customer, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid customer data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            customer = serializer.save(updated_by=request.user)
            
            logger.info(f"Customer updated: {customer.name} by {request.user.email}")
            
            return success_response(
                data=CustomerSerializer(customer).data,
                message='Customer updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update customer: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update customer',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            # Soft delete
            customer.delete()
            
            logger.info(f"Customer deleted: {customer.name} by {request.user.email}")
            
            return success_response(
                message='Customer deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete customer: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete customer',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Customers'],
    summary='Invite customer',
    description='Send an invitation to a customer to access the system',
    request=InviteCustomerSerializer,
    responses={
        200: CustomerInvitationSerializer,
        400: {'description': 'Invalid invitation data'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminManagerOwner])
def customer_invite(request):
    """
    Send an invitation to a customer.
    """
    serializer = InviteCustomerSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid invitation data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            customer = serializer.customer
            email = serializer.validated_data['email']
            
            # Revoke any existing pending invitations
            CustomerInvitation.objects.filter(
                customer=customer,
                email=email,
                status='pending'
            ).update(status='revoked')
            
            # Create new invitation
            invitation = CustomerInvitation.objects.create(
                customer=customer,
                email=email,
                invited_by=request.user
            )
            
            # Send invitation email
            send_customer_invitation_email(invitation)
            
            logger.info(f"Customer invitation sent: {email} by {request.user.email}")
            
            return success_response(
                data=CustomerInvitationSerializer(invitation).data,
                message='Invitation sent successfully'
            )
    except Exception as e:
        logger.error(f"Failed to send invitation: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to send invitation',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customers'],
    summary='Get customer assets',
    description='Get all facilities, buildings, and equipment assigned to a customer',
    responses={
        200: {'description': 'Customer assets retrieved successfully'},
        404: {'description': 'Customer not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_assets(request, customer_id):
    """
    Get all assets (facilities, buildings, equipment) assigned to a customer.
    """
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return error_response(
            message='Customer not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Get assigned facilities
        facilities = customer.facilities.all()
        
        # Get assigned buildings
        buildings = customer.buildings.all()
        
        # Get assigned equipment
        equipment = customer.equipment_items.all()
        
        data = {
            'customer': CustomerSerializer(customer).data,
            'facilities': {
                'count': facilities.count(),
                'items': [{'id': str(f.id), 'name': f.name, 'code': f.code} for f in facilities]
            },
            'buildings': {
                'count': buildings.count(),
                'items': [{'id': str(b.id), 'name': b.name, 'code': b.code} for b in buildings]
            },
            'equipment': {
                'count': equipment.count(),
                'items': [{'id': str(e.id), 'name': e.name, 'equipment_number': e.equipment_number} for e in equipment]
            }
        }
        
        return success_response(
            data=data,
            message='Customer assets retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get customer assets: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve customer assets',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customers'],
    summary='Verify customer invitation',
    description='Verify a customer invitation token (public endpoint - no auth required)',
    request=AcceptInvitationSerializer,
    responses={
        200: CustomerInvitationSerializer,
        400: {'description': 'Invalid or expired invitation'},
    }
)
@api_view(['POST'])
@permission_classes([])  # Public endpoint
def verify_customer_invitation(request):
    """
    Verify a customer invitation token.
    This is a public endpoint that customers can use to check if their invitation is valid
    before registering.
    
    Multi-tenant aware: searches across all tenant schemas to find the invitation.
    """
    serializer = AcceptInvitationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid invitation data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from django_tenants.utils import schema_context
        
        invitation = serializer.invitation
        tenant = serializer.tenant
        
        # Return invitation data with tenant context
        with schema_context(tenant.schema_name):
            invitation_data = CustomerInvitationSerializer(invitation).data
            invitation_data['tenant_slug'] = tenant.slug
            invitation_data['tenant_name'] = tenant.name
        
        return success_response(
            data=invitation_data,
            message='Invitation is valid'
        )
    except Exception as e:
        logger.error(f"Failed to verify invitation: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to verify invitation',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customers'],
    summary='Accept customer invitation',
    description='Accept a customer invitation and link user account (requires authentication)',
    request=AcceptInvitationSerializer,
    responses={
        200: {'description': 'Invitation accepted successfully'},
        400: {'description': 'Invalid or expired invitation'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_customer_invitation(request):
    """
    Accept a customer invitation.
    User must be authenticated to accept the invitation.
    
    Multi-tenant aware: searches across all tenant schemas to find the invitation,
    then switches to that tenant's schema to accept it.
    """
    serializer = AcceptInvitationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid invitation data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from django_tenants.utils import schema_context
        
        invitation = serializer.invitation
        tenant = serializer.tenant
        
        with transaction.atomic():
            # Switch to the tenant's schema to perform the acceptance
            with schema_context(tenant.schema_name):
                # Re-fetch the invitation in the correct schema context
                invitation = CustomerInvitation.objects.get(token=serializer.validated_data['token'])
                
                # Verify email matches
                if invitation.email.lower() != request.user.email.lower():
                    return error_response(
                        message='Invitation email does not match your account email',
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                # Accept invitation and link user
                invitation.accept(request.user)
                
                # Create tenant membership for the customer
                from apps.tenants.models import TenantMember
                TenantMember.objects.get_or_create(
                    tenant=tenant,
                    user=request.user,
                    defaults={'role': 'customer'}
                )
                
                logger.info(f"Customer invitation accepted: {invitation.email} by {request.user.email} for tenant {tenant.slug}")
                
                return success_response(
                    data={
                        'customer': CustomerSerializer(invitation.customer).data,
                        'invitation': CustomerInvitationSerializer(invitation).data,
                        'tenant_slug': tenant.slug,
                        'tenant_name': tenant.name
                    },
                    message='Invitation accepted successfully'
                )
    except Exception as e:
        logger.error(f"Failed to accept invitation: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to accept invitation',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Customers'],
    summary='Get or update customer profile',
    description='Get the authenticated customer\'s profile information or update it',
    request=UpdateCustomerSerializer,
    responses={
        200: CustomerSerializer,
        400: {'description': 'Invalid data or not a customer'},
        404: {'description': 'Customer profile not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@with_customer_tenant_context
def update_customer_profile(request):
    """
    Get or update customer profile.
    Only accessible by customers (users with linked customer profiles).
    """
    try:
        # Check if user has a customer profile
        if not hasattr(request.user, 'customer_profile') or not request.user.customer_profile:
            return error_response(
                message='No customer profile found for this user',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        customer = request.user.customer_profile
        
        # GET request - return customer profile
        if request.method == 'GET':
            return success_response(
                data=CustomerSerializer(customer).data,
                message='Customer profile retrieved successfully'
            )
        
        # PUT/PATCH request - update customer profile
        # Use partial update for PATCH
        partial = request.method == 'PATCH'
        serializer = UpdateCustomerSerializer(customer, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid customer data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        logger.info(f"Customer profile updated: {customer.email} by {request.user.email}")
        
        return success_response(
            data=CustomerSerializer(customer).data,
            message='Profile updated successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get/update customer profile: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to process request',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# Facility Views

@extend_schema(
    tags=['Facilities'],
    summary='List and create facilities',
    description='Get paginated list of facilities with filtering and search, or create a new facility',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('status', str, description='Filter by operational status'),
        OpenApiParameter('type', str, description='Filter by facility type'),
        OpenApiParameter('customer', str, description='Filter by customer ID'),
        OpenApiParameter('search', str, description='Search by name or code'),
    ],
    request=CreateFacilitySerializer,
    responses={
        200: FacilityListSerializer(many=True),
        201: FacilitySerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee', 'customer'],
    POST=['admin', 'manager', 'owner']
)
@with_customer_tenant_context
def facility_list_create(request):
    """
    List facilities with pagination and filtering, or create a new facility.
    """
    
    if request.method == 'GET':
        # Get queryset based on user role
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            # Customers only see facilities assigned to them
            try:
                customer = request.user.customer_profile
                queryset = Facility.objects.filter(customer=customer)
            except:
                queryset = Facility.objects.none()
        else:
            # Staff users see all facilities
            queryset = Facility.objects.all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(operational_status=status_filter)
        
        type_filter = request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(facility_type=type_filter)
        
        customer_filter = request.query_params.get('customer')
        if customer_filter:
            queryset = queryset.filter(customer_id=customer_filter)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = FacilityListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Facilities retrieved successfully'
            })
        
        serializer = FacilityListSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Facilities retrieved successfully'
        )
    
    elif request.method == 'POST':
        serializer = CreateFacilitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid facility data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                facility = serializer.save(created_by=request.user)
                
                logger.info(f"Facility created: {facility.name} by {request.user.email}")
                
                return success_response(
                    data=FacilitySerializer(facility).data,
                    message='Facility created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create facility: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create facility',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Facilities'],
    summary='Get, update, or delete facility',
    description='Retrieve facility details, update facility information, or soft delete a facility',
    request=UpdateFacilitySerializer,
    responses={
        200: FacilitySerializer,
        404: {'description': 'Facility not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee', 'customer'],
    PUT=['admin', 'manager', 'owner'],
    PATCH=['admin', 'manager', 'owner'],
    DELETE=['admin', 'manager', 'owner']
)
@with_customer_tenant_context
def facility_detail(request, facility_id):
    """
    Retrieve, update, or delete a facility.
    """
    try:
        facility = Facility.objects.get(pk=facility_id)
        
        # Check customer access
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            try:
                customer = request.user.customer_profile
                if facility.customer != customer:
                    return error_response(
                        message='You do not have access to this facility',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this facility',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Facility.DoesNotExist:
        return error_response(
            message='Facility not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = FacilitySerializer(facility)
        return success_response(
            data=serializer.data,
            message='Facility retrieved successfully'
        )
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UpdateFacilitySerializer(facility, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid facility data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            facility = serializer.save(updated_by=request.user)
            
            logger.info(f"Facility updated: {facility.name} by {request.user.email}")
            
            return success_response(
                data=FacilitySerializer(facility).data,
                message='Facility updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update facility: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update facility',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            # Soft delete (will cascade to buildings and equipment)
            facility.delete()
            
            logger.info(f"Facility deleted: {facility.name} by {request.user.email}")
            
            return success_response(
                message='Facility deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete facility: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete facility',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Facilities'],
    summary='Get facility buildings',
    description='Get all buildings within a facility',
    responses={
        200: {'description': 'Buildings retrieved successfully'},
        404: {'description': 'Facility not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facility_buildings(request, facility_id):
    """
    Get all buildings in a facility.
    """
    try:
        facility = Facility.objects.get(pk=facility_id)
        
        # Check customer access
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            try:
                customer = request.user.customer_profile
                if facility.customer != customer:
                    return error_response(
                        message='You do not have access to this facility',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this facility',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Facility.DoesNotExist:
        return error_response(
            message='Facility not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        buildings = facility.buildings.all()
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(buildings, request)
        
        # Import BuildingListSerializer (will be created in next task)
        from .serializers import BuildingListSerializer
        
        if page is not None:
            serializer = BuildingListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Buildings retrieved successfully'
            })
        
        serializer = BuildingListSerializer(buildings, many=True)
        return success_response(
            data=serializer.data,
            message='Buildings retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get facility buildings: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve buildings',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Facilities'],
    summary='Get facility equipment',
    description='Get all equipment within a facility (across all buildings)',
    responses={
        200: {'description': 'Equipment retrieved successfully'},
        404: {'description': 'Facility not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facility_equipment(request, facility_id):
    """
    Get all equipment in a facility (across all buildings).
    """
    try:
        facility = Facility.objects.get(pk=facility_id)
        
        # Check customer access
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            try:
                customer = request.user.customer_profile
                if facility.customer != customer:
                    return error_response(
                        message='You do not have access to this facility',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this facility',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Facility.DoesNotExist:
        return error_response(
            message='Facility not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        from apps.equipment.models import Equipment
        equipment = Equipment.objects.filter(building__facility=facility)
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(equipment, request)
        
        # Import EquipmentListSerializer (will be created in next task)
        from apps.equipment.serializers import EquipmentListSerializer
        
        if page is not None:
            serializer = EquipmentListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Equipment retrieved successfully'
            })
        
        serializer = EquipmentListSerializer(equipment, many=True)
        return success_response(
            data=serializer.data,
            message='Equipment retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get facility equipment: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve equipment',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




# Building Views

@extend_schema(
    tags=['Buildings'],
    summary='List and create buildings',
    description='Get paginated list of buildings with filtering and search, or create a new building',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('facility', str, description='Filter by facility ID'),
        OpenApiParameter('status', str, description='Filter by operational status'),
        OpenApiParameter('type', str, description='Filter by building type'),
        OpenApiParameter('customer', str, description='Filter by customer ID'),
        OpenApiParameter('search', str, description='Search by name or code'),
    ],
    request=CreateBuildingSerializer,
    responses={
        200: BuildingListSerializer(many=True),
        201: BuildingSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee', 'customer'],
    POST=['admin', 'manager', 'owner']
)
@with_customer_tenant_context
def building_list_create(request):
    """
    List buildings with pagination and filtering, or create a new building.
    """
    if request.method == 'GET':
        # Get queryset based on user role
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            # Customers only see buildings assigned to them or in their facilities
            try:
                customer = request.user.customer_profile
                queryset = Building.objects.filter(
                    Q(customer=customer) | Q(facility__customer=customer)
                )
            except:
                queryset = Building.objects.none()
        else:
            # Staff users see all buildings
            queryset = Building.objects.all()
        
        # Apply filters
        facility_filter = request.query_params.get('facility')
        if facility_filter:
            queryset = queryset.filter(facility_id=facility_filter)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(operational_status=status_filter)
        
        type_filter = request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(building_type=type_filter)
        
        customer_filter = request.query_params.get('customer')
        if customer_filter:
            queryset = queryset.filter(customer_id=customer_filter)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = BuildingListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Buildings retrieved successfully'
            })
        
        serializer = BuildingListSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Buildings retrieved successfully'
        )
    
    elif request.method == 'POST':
        serializer = CreateBuildingSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid building data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                building = serializer.save(created_by=request.user)
                
                logger.info(f"Building created: {building.name} by {request.user.email}")
                
                return success_response(
                    data=BuildingSerializer(building).data,
                    message='Building created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create building: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create building',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Buildings'],
    summary='Get, update, or delete building',
    description='Retrieve building details, update building information, or soft delete a building',
    request=UpdateBuildingSerializer,
    responses={
        200: BuildingSerializer,
        404: {'description': 'Building not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, MethodRolePermission])
@method_role_permissions(
    GET=['admin', 'manager', 'owner', 'technician', 'employee', 'customer'],
    PUT=['admin', 'manager', 'owner'],
    PATCH=['admin', 'manager', 'owner'],
    DELETE=['admin', 'manager', 'owner']
)
@with_customer_tenant_context
def building_detail(request, building_id):
    """
    Retrieve, update, or delete a building.
    """
    try:
        building = Building.objects.get(pk=building_id)
        
        # Check customer access
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            try:
                customer = request.user.customer_profile
                if building.customer != customer and building.facility.customer != customer:
                    return error_response(
                        message='You do not have access to this building',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this building',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Building.DoesNotExist:
        return error_response(
            message='Building not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = BuildingSerializer(building)
        return success_response(
            data=serializer.data,
            message='Building retrieved successfully'
        )
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UpdateBuildingSerializer(building, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid building data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            building = serializer.save(updated_by=request.user)
            
            logger.info(f"Building updated: {building.name} by {request.user.email}")
            
            return success_response(
                data=BuildingSerializer(building).data,
                message='Building updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update building: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update building',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            # Soft delete (will cascade to equipment)
            building.delete()
            
            logger.info(f"Building deleted: {building.name} by {request.user.email}")
            
            return success_response(
                message='Building deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete building: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete building',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Buildings'],
    summary='Get building equipment',
    description='Get all equipment within a building',
    responses={
        200: {'description': 'Equipment retrieved successfully'},
        404: {'description': 'Building not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def building_equipment(request, building_id):
    """
    Get all equipment in a building.
    """
    try:
        building = Building.objects.get(pk=building_id)
        
        # Check customer access
        ensure_tenant_role(request)
        if getattr(request, 'tenant_role', None) == 'customer':
            try:
                customer = request.user.customer_profile
                if building.customer != customer and building.facility.customer != customer:
                    return error_response(
                        message='You do not have access to this building',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this building',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Building.DoesNotExist:
        return error_response(
            message='Building not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        equipment = building.equipment_items.all()
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(equipment, request)
        
        # Import EquipmentListSerializer (will be created in next task)
        from apps.equipment.serializers import EquipmentListSerializer
        
        if page is not None:
            serializer = EquipmentListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Equipment retrieved successfully'
            })
        
        serializer = EquipmentListSerializer(equipment, many=True)
        return success_response(
            data=serializer.data,
            message='Equipment retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get building equipment: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve equipment',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




# Location Views

@extend_schema(
    tags=['Locations'],
    summary='List and create locations',
    description='Get list of locations with filtering, or create a new location',
    parameters=[
        OpenApiParameter('entity_type', str, description='Filter by entity type (facility, building, equipment, etc.)'),
        OpenApiParameter('entity_id', str, description='Filter by entity ID'),
    ],
    request=CreateLocationSerializer,
    responses={
        200: LocationSerializer(many=True),
        201: LocationSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def location_list_create(request):
    """
    List locations with filtering, or create a new location.
    """
    if request.method == 'GET':
        queryset = Location.objects.all()
        
        # Apply filters
        entity_type = request.query_params.get('entity_type')
        if entity_type:
            from django.contrib.contenttypes.models import ContentType
            try:
                content_type = ContentType.objects.get(model=entity_type.lower())
                queryset = queryset.filter(content_type=content_type)
            except ContentType.DoesNotExist:
                pass
        
        entity_id = request.query_params.get('entity_id')
        if entity_id:
            queryset = queryset.filter(object_id=entity_id)
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        serializer = LocationSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Locations retrieved successfully'
        )
    
    elif request.method == 'POST':
        serializer = CreateLocationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid location data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                location = serializer.save(created_by=request.user)
                
                logger.info(f"Location created: {location.name} by {request.user.email}")
                
                return success_response(
                    data=LocationSerializer(location).data,
                    message='Location created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create location: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create location',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Locations'],
    summary='Get, update, or delete location',
    description='Retrieve location details, update location information, or delete a location',
    request=UpdateLocationSerializer,
    responses={
        200: LocationSerializer,
        404: {'description': 'Location not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def location_detail(request, location_id):
    """
    Retrieve, update, or delete a location.
    """
    try:
        location = Location.objects.get(pk=location_id)
    except Location.DoesNotExist:
        return error_response(
            message='Location not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = LocationSerializer(location)
        return success_response(
            data=serializer.data,
            message='Location retrieved successfully'
        )
    
    elif request.method in ['PUT', 'PATCH']:
        partial = request.method == 'PATCH'
        serializer = UpdateLocationSerializer(location, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid location data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = serializer.save()
            
            logger.info(f"Location updated: {location.name} by {request.user.email}")
            
            return success_response(
                data=LocationSerializer(location).data,
                message='Location updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update location: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update location',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            location.delete()
            
            logger.info(f"Location deleted: {location.name} by {request.user.email}")
            
            return success_response(
                message='Location deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete location: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete location',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

