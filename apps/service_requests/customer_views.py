"""
Customer Portal Views

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
import logging

from .models import ServiceRequest
from apps.equipment.models import Equipment
from apps.tasks.models import Task
from apps.core.responses import success_response, error_response

logger = logging.getLogger(__name__)


# Task 12: Customer Equipment Visibility

@extend_schema(
    tags=['Customer Portal'],
    summary='List customer equipment',
    description='List all equipment belonging to the customer',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('facility', str, description='Filter by facility ID'),
    ],
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_equipment_list(request):
    """
    List customer's equipment.
    Task 12.1: Customer equipment endpoints
    """
    # Only customers can access
    if request.user.role != 'customer':
        return error_response(
            message='This endpoint is for customers only',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get customer's equipment
    queryset = Equipment.objects.filter(customer=request.user)
    
    # Apply filters
    facility_filter = request.query_params.get('facility')
    if facility_filter:
        queryset = queryset.filter(facility_id=facility_filter)
    
    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get('page_size', 20))
    paginator.max_page_size = 100
    
    page = paginator.paginate_queryset(queryset, request)
    
    # Serialize equipment data (exclude internal fields)
    equipment_data = []
    for equipment in (page if page else queryset):
        equipment_data.append({
            'id': str(equipment.id),
            'name': equipment.name,
            'equipment_type': equipment.equipment_type,
            'manufacturer': equipment.manufacturer,
            'model': equipment.model,
            'serial_number': equipment.serial_number,
            'location': equipment.location,
            'status': equipment.status,
            'facility': {
                'id': str(equipment.facility.id),
                'name': equipment.facility.name,
            } if equipment.facility else None,
            'building': {
                'id': str(equipment.building.id),
                'name': equipment.building.name,
            } if equipment.building else None,
            'installation_date': equipment.installation_date,
            'warranty_expiry': equipment.warranty_expiry,
            # Exclude: purchase_cost, maintenance_cost, notes (internal)
        })
    
    if page is not None:
        return paginator.get_paginated_response(equipment_data)
    
    return success_response(data=equipment_data)


@extend_schema(
    tags=['Customer Portal'],
    summary='Get equipment details',
    description='Get detailed information about a specific equipment',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_equipment_detail(request, equipment_id):
    """
    Get equipment details.
    Task 12.1: Customer equipment endpoints
    """
    # Only customers can access
    if request.user.role != 'customer':
        return error_response(
            message='This endpoint is for customers only',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        equipment = Equipment.objects.get(pk=equipment_id)
    except Equipment.DoesNotExist:
        return error_response(
            message='Equipment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check ownership
    if equipment.customer != request.user:
        return error_response(
            message='You can only view your own equipment',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Serialize equipment data (exclude internal fields)
    equipment_data = {
        'id': str(equipment.id),
        'name': equipment.name,
        'equipment_type': equipment.equipment_type,
        'manufacturer': equipment.manufacturer,
        'model': equipment.model,
        'serial_number': equipment.serial_number,
        'location': equipment.location,
        'status': equipment.status,
        'facility': {
            'id': str(equipment.facility.id),
            'name': equipment.facility.name,
            'address': equipment.facility.address,
        } if equipment.facility else None,
        'building': {
            'id': str(equipment.building.id),
            'name': equipment.building.name,
        } if equipment.building else None,
        'installation_date': equipment.installation_date,
        'warranty_expiry': equipment.warranty_expiry,
        'specifications': equipment.specifications,
        # Exclude: purchase_cost, maintenance_cost, notes (internal)
    }
    
    return success_response(data=equipment_data)


@extend_schema(
    tags=['Customer Portal'],
    summary='Get equipment service history',
    description='Get service history for a specific equipment',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_equipment_history(request, equipment_id):
    """
    Get equipment service history.
    Task 12.2: Equipment service history endpoint
    """
    # Only customers can access
    if request.user.role != 'customer':
        return error_response(
            message='This endpoint is for customers only',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        equipment = Equipment.objects.get(pk=equipment_id)
    except Equipment.DoesNotExist:
        return error_response(
            message='Equipment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check ownership
    if equipment.customer != request.user:
        return error_response(
            message='You can only view history for your own equipment',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get service requests
    service_requests = ServiceRequest.objects.filter(
        equipment=equipment,
        customer=request.user
    ).order_by('-created_at')
    
    # Get completed tasks
    completed_tasks = Task.objects.filter(
        equipment=equipment,
        status='completed'
    ).order_by('-created_at')
    
    history_data = {
        'equipment': {
            'id': str(equipment.id),
            'name': equipment.name,
        },
        'service_requests': [
            {
                'id': str(req.id),
                'request_number': req.request_number,
                'title': req.title,
                'request_type': req.request_type,
                'status': req.status,
                'created_at': req.created_at,
                'completed_at': req.completed_at,
            }
            for req in service_requests[:10]  # Last 10 requests
        ],
        'completed_tasks': [
            {
                'id': str(task.id),
                'task_number': task.task_number,
                'title': task.title,
                'completed_at': task.updated_at,
            }
            for task in completed_tasks[:10]  # Last 10 tasks
        ],
    }
    
    return success_response(data=history_data)


@extend_schema(
    tags=['Customer Portal'],
    summary='Get upcoming services',
    description='Get upcoming scheduled services for equipment',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_equipment_upcoming(request, equipment_id):
    """
    Get upcoming services for equipment.
    Task 12.3: Upcoming services endpoint
    """
    # Only customers can access
    if request.user.role != 'customer':
        return error_response(
            message='This endpoint is for customers only',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        equipment = Equipment.objects.get(pk=equipment_id)
    except Equipment.DoesNotExist:
        return error_response(
            message='Equipment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check ownership
    if equipment.customer != request.user:
        return error_response(
            message='You can only view upcoming services for your own equipment',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get pending service requests
    pending_requests = ServiceRequest.objects.filter(
        equipment=equipment,
        customer=request.user,
        status__in=['pending', 'under_review', 'accepted', 'in_progress']
    ).order_by('created_at')
    
    # Get scheduled tasks
    scheduled_tasks = Task.objects.filter(
        equipment=equipment,
        status__in=['pending', 'assigned', 'in_progress'],
        scheduled_start__gte=timezone.now()
    ).order_by('scheduled_start')
    
    upcoming_data = {
        'equipment': {
            'id': str(equipment.id),
            'name': equipment.name,
        },
        'pending_requests': [
            {
                'id': str(req.id),
                'request_number': req.request_number,
                'title': req.title,
                'status': req.status,
                'priority': req.priority,
                'created_at': req.created_at,
                'estimated_timeline': req.estimated_timeline,
            }
            for req in pending_requests
        ],
        'scheduled_tasks': [
            {
                'id': str(task.id),
                'task_number': task.task_number,
                'title': task.title,
                'status': task.status,
                'scheduled_start': task.scheduled_start,
                'scheduled_end': task.scheduled_end,
            }
            for task in scheduled_tasks
        ],
    }
    
    return success_response(data=upcoming_data)


# Task 13: Customer Dashboard

@extend_schema(
    tags=['Customer Portal'],
    summary='Get customer dashboard',
    description='Get dashboard metrics and recent activity for customer',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_dashboard(request):
    """
    Get customer dashboard metrics.
    Task 13.1: Dashboard metrics endpoint
    """
    # Only customers can access
    if request.user.role != 'customer':
        return error_response(
            message='This endpoint is for customers only',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get request counts
    requests_pending = ServiceRequest.objects.filter(
        customer=request.user,
        status='pending'
    ).count()
    
    requests_in_progress = ServiceRequest.objects.filter(
        customer=request.user,
        status='in_progress'
    ).count()
    
    requests_completed = ServiceRequest.objects.filter(
        customer=request.user,
        status='completed'
    ).count()
    
    # Get recent activity
    recent_requests = ServiceRequest.objects.filter(
        customer=request.user
    ).order_by('-updated_at')[:5]
    
    # Get equipment requiring attention
    equipment_with_issues = Equipment.objects.filter(
        customer=request.user,
        status__in=['maintenance_required', 'out_of_service']
    )
    
    # Get upcoming scheduled services
    upcoming_tasks = Task.objects.filter(
        equipment__customer=request.user,
        status__in=['pending', 'assigned'],
        scheduled_start__gte=timezone.now()
    ).order_by('scheduled_start')[:5]
    
    dashboard_data = {
        'metrics': {
            'pending_requests': requests_pending,
            'in_progress_requests': requests_in_progress,
            'completed_requests': requests_completed,
            'total_equipment': Equipment.objects.filter(customer=request.user).count(),
            'equipment_requiring_attention': equipment_with_issues.count(),
        },
        'recent_activity': [
            {
                'id': str(req.id),
                'request_number': req.request_number,
                'title': req.title,
                'status': req.status,
                'updated_at': req.updated_at,
            }
            for req in recent_requests
        ],
        'equipment_requiring_attention': [
            {
                'id': str(eq.id),
                'name': eq.name,
                'status': eq.status,
                'location': eq.location,
            }
            for eq in equipment_with_issues[:5]
        ],
        'upcoming_services': [
            {
                'id': str(task.id),
                'task_number': task.task_number,
                'equipment_name': task.equipment.name if task.equipment else None,
                'scheduled_start': task.scheduled_start,
            }
            for task in upcoming_tasks
        ],
    }
    
    return success_response(data=dashboard_data)
