"""
Equipment Views

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

from .models import Equipment
from .serializers import (
    EquipmentSerializer, CreateEquipmentSerializer, UpdateEquipmentSerializer,
    EquipmentListSerializer
)
from apps.core.responses import success_response, error_response

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Equipment'],
    summary='List and create equipment',
    description='Get paginated list of equipment with filtering and search, or create new equipment',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('building', str, description='Filter by building ID'),
        OpenApiParameter('facility', str, description='Filter by facility ID'),
        OpenApiParameter('status', str, description='Filter by operational status'),
        OpenApiParameter('type', str, description='Filter by equipment type'),
        OpenApiParameter('manufacturer', str, description='Filter by manufacturer'),
        OpenApiParameter('customer', str, description='Filter by customer ID'),
        OpenApiParameter('search', str, description='Search by name or equipment number'),
    ],
    request=CreateEquipmentSerializer,
    responses={
        200: EquipmentListSerializer(many=True),
        201: EquipmentSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def equipment_list_create(request):
    """
    List equipment with pagination and filtering, or create new equipment.
    """
    if request.method == 'GET':
        # Get queryset based on user role
        if request.tenant_role == 'customer':
            # Customers only see equipment assigned to them or in their facilities/buildings
            try:
                customer = request.user.customer_profile
                queryset = Equipment.objects.filter(
                    Q(customer=customer) |
                    Q(building__customer=customer) |
                    Q(building__facility__customer=customer)
                )
            except:
                queryset = Equipment.objects.none()
        else:
            # Staff users see all equipment
            queryset = Equipment.objects.all()
        
        # Apply filters
        building_filter = request.query_params.get('building')
        if building_filter:
            queryset = queryset.filter(building_id=building_filter)
        
        facility_filter = request.query_params.get('facility')
        if facility_filter:
            queryset = queryset.filter(building__facility_id=facility_filter)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(operational_status=status_filter)
        
        type_filter = request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(equipment_type=type_filter)
        
        manufacturer_filter = request.query_params.get('manufacturer')
        if manufacturer_filter:
            queryset = queryset.filter(manufacturer__icontains=manufacturer_filter)
        
        customer_filter = request.query_params.get('customer')
        if customer_filter:
            queryset = queryset.filter(customer_id=customer_filter)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(equipment_number__icontains=search)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = EquipmentListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Equipment retrieved successfully'
            })
        
        serializer = EquipmentListSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Equipment retrieved successfully'
        )
    
    elif request.method == 'POST':
        # Check permissions (owner/admin/manager only)
        from apps.facilities.views import require_role
        error = require_role(request, ['owner', 'admin', 'manager'])
        if error:
            return error
        
        serializer = CreateEquipmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid equipment data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                equipment = serializer.save(created_by=request.user)
                
                logger.info(f"Equipment created: {equipment.name} ({equipment.equipment_number}) by {request.user.email}")
                
                return success_response(
                    data=EquipmentSerializer(equipment).data,
                    message='Equipment created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create equipment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create equipment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Equipment'],
    summary='Get, update, or delete equipment',
    description='Retrieve equipment details, update equipment information, or soft delete equipment',
    request=UpdateEquipmentSerializer,
    responses={
        200: EquipmentSerializer,
        404: {'description': 'Equipment not found'},
    }
)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def equipment_detail(request, equipment_id):
    """
    Retrieve, update, or delete equipment.
    """
    try:
        equipment = Equipment.objects.get(pk=equipment_id)
        
        # Check customer access
        if request.tenant_role == 'customer':
            try:
                customer = request.user.customer_profile
                if (equipment.customer != customer and
                    equipment.building.customer != customer and
                    equipment.building.facility.customer != customer):
                    return error_response(
                        message='You do not have access to this equipment',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this equipment',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Equipment.DoesNotExist:
        return error_response(
            message='Equipment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = EquipmentSerializer(equipment)
        return success_response(
            data=serializer.data,
            message='Equipment retrieved successfully'
        )
    
    elif request.method in ['PUT', 'PATCH']:
        # Check permissions (owner/admin/manager only)
        from apps.facilities.views import require_role
        error = require_role(request, ['owner', 'admin', 'manager'])
        if error:
            return error
        
        partial = request.method == 'PATCH'
        serializer = UpdateEquipmentSerializer(equipment, data=request.data, partial=partial)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid equipment data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            equipment = serializer.save(updated_by=request.user)
            
            logger.info(f"Equipment updated: {equipment.name} ({equipment.equipment_number}) by {request.user.email}")
            
            return success_response(
                data=EquipmentSerializer(equipment).data,
                message='Equipment updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update equipment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update equipment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        # Check permissions (owner/admin/manager only)
        from apps.facilities.views import require_role
        error = require_role(request, ['owner', 'admin', 'manager'])
        if error:
            return error
        
        try:
            # Soft delete
            equipment.delete()
            
            logger.info(f"Equipment deleted: {equipment.name} ({equipment.equipment_number}) by {request.user.email}")
            
            return success_response(
                message='Equipment deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete equipment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete equipment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Equipment'],
    summary='Get equipment history',
    description='Get audit history for equipment',
    responses={
        200: {'description': 'Equipment history retrieved successfully'},
        404: {'description': 'Equipment not found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def equipment_history(request, equipment_id):
    """
    Get equipment audit history.
    """
    try:
        equipment = Equipment.objects.get(pk=equipment_id)
        
        # Check customer access
        if request.tenant_role == 'customer':
            try:
                customer = request.user.customer_profile
                if (equipment.customer != customer and
                    equipment.building.customer != customer and
                    equipment.building.facility.customer != customer):
                    return error_response(
                        message='You do not have access to this equipment',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            except:
                return error_response(
                    message='You do not have access to this equipment',
                    status_code=status.HTTP_403_FORBIDDEN
                )
    except Equipment.DoesNotExist:
        return error_response(
            message='Equipment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Build history from audit fields
        history = {
            'equipment_number': equipment.equipment_number,
            'name': equipment.name,
            'created_by': equipment.created_by.full_name if equipment.created_by else None,
            'created_at': equipment.created_at,
            'updated_by': equipment.updated_by.full_name if equipment.updated_by else None,
            'updated_at': equipment.updated_at,
            'deleted_at': equipment.deleted_at,
        }
        
        return success_response(
            data=history,
            message='Equipment history retrieved successfully'
        )
    except Exception as e:
        logger.error(f"Failed to get equipment history: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to retrieve equipment history',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
