"""
Service Requests Views

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
import logging

from .models import ServiceRequest, RequestAction, RequestComment, RequestAttachment
from .serializers import (
    ServiceRequestSerializer, CustomerServiceRequestSerializer,
    CreateServiceRequestSerializer, UpdateServiceRequestSerializer,
    AcceptRequestSerializer, RejectRequestSerializer,
    ConvertToTaskSerializer, SubmitFeedbackSerializer,
    UpdateInternalNotesSerializer, RequestCommentSerializer,
    CreateCommentSerializer, RequestAttachmentSerializer,
    UploadAttachmentSerializer, RequestActionSerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import IsAdminUser
from apps.equipment.models import Equipment
from apps.tasks.models import Task, TaskAssignment, TaskAttachment

logger = logging.getLogger(__name__)


# Task 4: Customer Service Request Endpoints

@extend_schema(
    tags=['Service Requests'],
    summary='Create or list service requests',
    description='Create a new service request or list customer\'s requests',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('status', str, description='Filter by status'),
        OpenApiParameter('priority', str, description='Filter by priority'),
        OpenApiParameter('request_type', str, description='Filter by request type'),
    ],
    request=CreateServiceRequestSerializer,
    responses={
        200: CustomerServiceRequestSerializer(many=True),
        201: CustomerServiceRequestSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def service_request_list_create(request):
    """
    List customer's service requests or create a new one.
    Task 4.1 & 4.2: Request submission and listing
    """
    if request.method == 'GET':
        # Only customers can use this endpoint for listing
        if request.user.role != 'customer':
            return error_response(
                message='This endpoint is for customers only. Admins should use /admin/ endpoint.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Get customer's requests only
        queryset = ServiceRequest.objects.filter(customer=request.user)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        request_type_filter = request.query_params.get('request_type')
        if request_type_filter:
            queryset = queryset.filter(request_type=request_type_filter)
        
        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 20))
        paginator.max_page_size = 100
        
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = CustomerServiceRequestSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = CustomerServiceRequestSerializer(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        # Only customers can create requests
        if request.user.role != 'customer':
            return error_response(
                message='Only customers can create service requests.',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CreateServiceRequestSerializer(
            data=request.data,
            context={'customer': request.user}
        )
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid request data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Get equipment
                equipment = Equipment.objects.get(pk=serializer.validated_data['equipment_id'])
                
                # Create service request
                service_request = ServiceRequest.objects.create(
                    customer=request.user,
                    equipment=equipment,
                    facility=equipment.facility,
                    request_type=serializer.validated_data['request_type'],
                    title=serializer.validated_data['title'],
                    description=serializer.validated_data['description'],
                    priority=serializer.validated_data['priority'],
                    issue_type=serializer.validated_data.get('issue_type'),
                    severity=serializer.validated_data.get('severity'),
                )
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='created',
                    user=request.user,
                    description=f'Service request created by {request.user.full_name}',
                    metadata={
                        'request_type': service_request.request_type,
                        'priority': service_request.priority,
                    }
                )
                
                # TODO: Send notifications to admins
                
                logger.info(f"Service request created: {service_request.request_number} by {request.user.email}")
                
                return success_response(
                    data=CustomerServiceRequestSerializer(service_request, context={'request': request}).data,
                    message='Service request created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Equipment.DoesNotExist:
            return error_response(
                message='Equipment not found',
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to create service request: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create service request',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Service Requests'],
    summary='Get, update, or delete service request',
    description='Get service request details, update, or cancel',
    request=UpdateServiceRequestSerializer,
    responses={200: CustomerServiceRequestSerializer}
)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def service_request_detail(request, request_id):
    """
    Get, update, or delete a service request.
    Task 4.2 & 4.3: Request detail and update/cancellation
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions - customer can only access their own requests
    if request.user.role == 'customer' and service_request.customer != request.user:
        return error_response(
            message='You can only access your own service requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Use appropriate serializer based on user role
        if request.user.role in ['admin', 'manager']:
            serializer = ServiceRequestSerializer(service_request, context={'request': request})
        else:
            serializer = CustomerServiceRequestSerializer(service_request, context={'request': request})
        
        return success_response(data=serializer.data)
    
    elif request.method == 'PATCH':
        # Only customer can update their own requests
        if service_request.customer != request.user:
            return error_response(
                message='You can only update your own service requests',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Can only update if not yet reviewed
        if not service_request.can_be_modified:
            return error_response(
                message='Cannot modify request after it has been reviewed',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = UpdateServiceRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid request data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Update fields
                for field, value in serializer.validated_data.items():
                    setattr(service_request, field, value)
                
                service_request.save()
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='updated',
                    user=request.user,
                    description=f'Service request updated by {request.user.full_name}',
                    metadata={'updated_fields': list(serializer.validated_data.keys())}
                )
                
                logger.info(f"Service request updated: {service_request.request_number}")
                
                return success_response(
                    data=CustomerServiceRequestSerializer(service_request, context={'request': request}).data,
                    message='Service request updated successfully'
                )
        except Exception as e:
            logger.error(f"Failed to update service request: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update service request',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        # Only customer can cancel their own requests
        if service_request.customer != request.user:
            return error_response(
                message='You can only cancel your own service requests',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                service_request.cancel()
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='cancelled',
                    user=request.user,
                    description=f'Service request cancelled by {request.user.full_name}'
                )
                
                logger.info(f"Service request cancelled: {service_request.request_number}")
                
                return success_response(message='Service request cancelled successfully')
        except Exception as e:
            logger.error(f"Failed to cancel service request: {str(e)}", exc_info=True)
            return error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )



# Task 6: Admin Review Endpoints

@extend_schema(
    tags=['Service Requests - Admin'],
    summary='List all service requests (Admin)',
    description='List all service requests with filters (Admin/Manager only)',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('status', str, description='Filter by status'),
        OpenApiParameter('priority', str, description='Filter by priority'),
        OpenApiParameter('customer', str, description='Filter by customer ID'),
        OpenApiParameter('equipment', str, description='Filter by equipment ID'),
    ],
    responses={200: ServiceRequestSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_service_request_list(request):
    """
    List all service requests (Admin/Manager only).
    Task 6.1: Admin request listing
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can access this endpoint',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get all requests
    queryset = ServiceRequest.objects.all()
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    priority_filter = request.query_params.get('priority')
    if priority_filter:
        queryset = queryset.filter(priority=priority_filter)
    
    customer_filter = request.query_params.get('customer')
    if customer_filter:
        queryset = queryset.filter(customer_id=customer_filter)
    
    equipment_filter = request.query_params.get('equipment')
    if equipment_filter:
        queryset = queryset.filter(equipment_id=equipment_filter)
    
    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get('page_size', 20))
    paginator.max_page_size = 100
    
    page = paginator.paginate_queryset(queryset, request)
    if page is not None:
        serializer = ServiceRequestSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)
    
    serializer = ServiceRequestSerializer(queryset, many=True, context={'request': request})
    return success_response(data=serializer.data)


@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Mark request under review',
    description='Mark a service request as under review',
    responses={200: ServiceRequestSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_under_review(request, request_id):
    """
    Mark a service request as under review.
    Task 6.2: Request review endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can review requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        with transaction.atomic():
            service_request.mark_under_review(request.user)
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='reviewed',
                user=request.user,
                description=f'Request marked under review by {request.user.full_name}'
            )
            
            logger.info(f"Request marked under review: {service_request.request_number}")
            
            return success_response(
                data=ServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Request marked under review'
            )
    except Exception as e:
        logger.error(f"Failed to mark request under review: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to mark request under review',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Update internal notes',
    description='Update internal notes for a service request',
    request=UpdateInternalNotesSerializer,
    responses={200: ServiceRequestSerializer}
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_internal_notes(request, request_id):
    """
    Update internal notes for a service request.
    Task 6.3: Internal notes endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can update internal notes',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = UpdateInternalNotesSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            service_request.internal_notes = serializer.validated_data['internal_notes']
            service_request.save()
            
            logger.info(f"Internal notes updated: {service_request.request_number}")
            
            return success_response(
                data=ServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Internal notes updated successfully'
            )
    except Exception as e:
        logger.error(f"Failed to update internal notes: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to update internal notes',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Task 7: Request Acceptance and Rejection

@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Accept service request',
    description='Accept a service request with optional timeline and cost',
    request=AcceptRequestSerializer,
    responses={200: ServiceRequestSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_request(request, request_id):
    """
    Accept a service request.
    Task 7.1: Request acceptance endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can accept requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = AcceptRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            service_request.accept(
                reviewed_by=request.user,
                response_message=serializer.validated_data.get('response_message', ''),
                estimated_timeline=serializer.validated_data.get('estimated_timeline', ''),
                estimated_cost=serializer.validated_data.get('estimated_cost')
            )
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='accepted',
                user=request.user,
                description=f'Request accepted by {request.user.full_name}',
                metadata={
                    'estimated_timeline': service_request.estimated_timeline,
                    'response_message': service_request.response_message,
                }
            )
            
            # TODO: Send notification to customer
            
            logger.info(f"Request accepted: {service_request.request_number}")
            
            return success_response(
                data=ServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Request accepted successfully'
            )
    except Exception as e:
        logger.error(f"Failed to accept request: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to accept request',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Reject service request',
    description='Reject a service request with reason',
    request=RejectRequestSerializer,
    responses={200: ServiceRequestSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_request(request, request_id):
    """
    Reject a service request.
    Task 7.2: Request rejection endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can reject requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = RejectRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            service_request.reject(
                reviewed_by=request.user,
                rejection_reason=serializer.validated_data['rejection_reason']
            )
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='rejected',
                user=request.user,
                description=f'Request rejected by {request.user.full_name}',
                metadata={'rejection_reason': service_request.rejection_reason}
            )
            
            # TODO: Send notification to customer
            
            logger.info(f"Request rejected: {service_request.request_number}")
            
            return success_response(
                data=ServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Request rejected'
            )
    except Exception as e:
        logger.error(f"Failed to reject request: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to reject request',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Task 8: Task Conversion

@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Convert request to task',
    description='Convert an accepted service request into a task',
    request=ConvertToTaskSerializer,
    responses={200: ServiceRequestSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def convert_to_task(request, request_id):
    """
    Convert a service request to a task.
    Task 8.2: Convert-to-task endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can convert requests to tasks',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check if can be converted
    if not service_request.can_be_converted_to_task:
        return error_response(
            message='Request must be accepted and not already converted to task',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = ConvertToTaskSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create task from request (Task 8.1: TaskConverter logic)
            task = Task.objects.create(
                equipment=service_request.equipment,
                title=service_request.title,
                description=service_request.description,
                priority=serializer.validated_data.get('priority', service_request.priority),
                scheduled_start=serializer.validated_data.get('scheduled_start'),
                scheduled_end=serializer.validated_data.get('scheduled_end'),
            )
            
            # Link task to request
            service_request.converted_task = task
            service_request.mark_in_progress()
            
            # Copy attachments
            for attachment in service_request.attachments.all():
                TaskAttachment.objects.create(
                    task=task,
                    uploaded_by=attachment.uploaded_by,
                    file=attachment.file,
                    filename=attachment.filename,
                    file_size=attachment.file_size,
                    file_type=attachment.file_type,
                    is_image=attachment.is_image,
                )
            
            # Assign technicians if provided
            assignee_ids = serializer.validated_data.get('assignee_ids', [])
            for assignee_id in assignee_ids:
                from apps.authentication.models import User
                try:
                    assignee = User.objects.get(pk=assignee_id)
                    TaskAssignment.objects.create(
                        task=task,
                        assignee=assignee,
                    )
                except User.DoesNotExist:
                    pass
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='converted',
                user=request.user,
                description=f'Request converted to task {task.task_number} by {request.user.full_name}',
                metadata={'task_id': str(task.id), 'task_number': task.task_number}
            )
            
            # TODO: Send notification to customer
            
            logger.info(f"Request converted to task: {service_request.request_number} -> {task.task_number}")
            
            return success_response(
                data=ServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Request converted to task successfully'
            )
    except Exception as e:
        logger.error(f"Failed to convert request to task: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to convert request to task',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Task 9: Request Tracking and Timeline

@extend_schema(
    tags=['Service Requests'],
    summary='Get request timeline',
    description='Get complete timeline of actions for a service request',
    responses={200: RequestActionSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_timeline(request, request_id):
    """
    Get request timeline (all actions).
    Task 9.1: Request timeline endpoint
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions
    if request.user.role == 'customer' and service_request.customer != request.user:
        return error_response(
            message='You can only view timeline for your own requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Get all actions
    actions = service_request.actions.all().order_by('created_at')
    serializer = RequestActionSerializer(actions, many=True, context={'request': request})
    
    return success_response(data=serializer.data)


# Task 10: Comments and Communication

@extend_schema(
    tags=['Service Requests'],
    summary='List or add comments',
    description='List comments or add a new comment to a service request',
    request=CreateCommentSerializer,
    responses={
        200: RequestCommentSerializer(many=True),
        201: RequestCommentSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def request_comments(request, request_id):
    """
    List or add comments to a service request.
    Task 10.1: Comment endpoints
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions
    if request.user.role == 'customer' and service_request.customer != request.user:
        return error_response(
            message='You can only access comments for your own requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Get comments (filter internal for customers)
        if request.user.role in ['admin', 'manager']:
            comments = service_request.comments.all()
        else:
            comments = service_request.comments.filter(is_internal=False)
        
        serializer = RequestCommentSerializer(comments, many=True, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        serializer = CreateCommentSerializer(
            data=request.data,
            context={'user': request.user}
        )
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid comment data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                comment = RequestComment.objects.create(
                    request=service_request,
                    user=request.user,
                    comment_text=serializer.validated_data['comment_text'],
                    is_internal=serializer.validated_data.get('is_internal', False)
                )
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='commented',
                    user=request.user,
                    description=f'Comment added by {request.user.full_name}',
                    metadata={'is_internal': comment.is_internal}
                )
                
                logger.info(f"Comment added to request: {service_request.request_number}")
                
                return success_response(
                    data=RequestCommentSerializer(comment, context={'request': request}).data,
                    message='Comment added successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to add comment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to add comment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Service Requests'],
    summary='List or upload attachments',
    description='List attachments or upload a new file to a service request',
    request=UploadAttachmentSerializer,
    responses={
        200: RequestAttachmentSerializer(many=True),
        201: RequestAttachmentSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def request_attachments(request, request_id):
    """
    List or upload attachments to a service request.
    Task 10: Attachment endpoints
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions
    if request.user.role == 'customer' and service_request.customer != request.user:
        return error_response(
            message='You can only access attachments for your own requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        attachments = service_request.attachments.all()
        serializer = RequestAttachmentSerializer(attachments, many=True, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        serializer = UploadAttachmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid file data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                uploaded_file = serializer.validated_data['file']
                
                attachment = RequestAttachment.objects.create(
                    request=service_request,
                    uploaded_by=request.user,
                    file=uploaded_file,
                    filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type,
                )
                
                logger.info(f"File uploaded to request: {service_request.request_number}")
                
                return success_response(
                    data=RequestAttachmentSerializer(attachment, context={'request': request}).data,
                    message='File uploaded successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to upload file',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Service Requests'],
    summary='Submit feedback',
    description='Submit customer feedback and rating for a completed request',
    request=SubmitFeedbackSerializer,
    responses={200: CustomerServiceRequestSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request, request_id):
    """
    Submit customer feedback for a completed request.
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Only customer can submit feedback for their own requests
    if service_request.customer != request.user:
        return error_response(
            message='You can only submit feedback for your own requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    serializer = SubmitFeedbackSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid feedback data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            service_request.submit_feedback(
                rating=serializer.validated_data['rating'],
                feedback_text=serializer.validated_data.get('feedback_text', '')
            )
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='feedback',
                user=request.user,
                description=f'Feedback submitted by {request.user.full_name}',
                metadata={'rating': service_request.customer_rating}
            )
            
            logger.info(f"Feedback submitted for request: {service_request.request_number}")
            
            return success_response(
                data=CustomerServiceRequestSerializer(service_request, context={'request': request}).data,
                message='Feedback submitted successfully'
            )
    except Exception as e:
        logger.error(f"Failed to submit feedback: {str(e)}", exc_info=True)
        return error_response(
            message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )



# Task 17: Reporting and Analytics

@extend_schema(
    tags=['Service Requests - Reports'],
    summary='Get service request reports',
    description='Get comprehensive reports and analytics for service requests',
    parameters=[
        OpenApiParameter('start_date', str, description='Start date (YYYY-MM-DD)'),
        OpenApiParameter('end_date', str, description='End date (YYYY-MM-DD)'),
        OpenApiParameter('customer', str, description='Filter by customer ID'),
        OpenApiParameter('equipment', str, description='Filter by equipment ID'),
    ],
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_request_reports(request):
    """
    Get service request reports and analytics.
    Task 17.1: Admin reports endpoint
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can access reports',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    from .reports import ServiceRequestReports
    from datetime import datetime
    
    # Parse date parameters
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    customer_id = request.query_params.get('customer')
    equipment_id = request.query_params.get('equipment')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    try:
        # Get overview metrics
        overview = ServiceRequestReports.get_overview_metrics(start_date, end_date)
        
        # Get customer-specific metrics if requested
        customer_metrics = None
        if customer_id:
            customer_metrics = ServiceRequestReports.get_customer_metrics(
                customer_id, start_date, end_date
            )
        
        # Get equipment-specific metrics if requested
        equipment_metrics = None
        if equipment_id:
            equipment_metrics = ServiceRequestReports.get_equipment_metrics(
                equipment_id, start_date, end_date
            )
        
        # Get time series data if date range provided
        time_series = None
        if start_date and end_date:
            time_series = ServiceRequestReports.get_time_series_data(
                start_date, end_date, granularity='day'
            )
        
        report_data = {
            'overview': overview,
            'customer_metrics': customer_metrics,
            'equipment_metrics': equipment_metrics,
            'time_series': time_series,
        }
        
        return success_response(data=report_data)
        
    except Exception as e:
        logger.error(f"Failed to generate reports: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to generate reports',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Service Requests - Reports'],
    summary='Get admin dashboard analytics',
    description='Get analytics for admin dashboard',
    responses={200: dict}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_analytics(request):
    """
    Get admin dashboard analytics.
    Task 17.2: Dashboard analytics
    """
    # Only admin/manager can access
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can access analytics',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    from .reports import ServiceRequestReports
    
    try:
        analytics_data = {
            'pending_requests': ServiceRequestReports.get_pending_requests_count(),
            'overdue_requests': ServiceRequestReports.get_overdue_requests(),
            'customer_satisfaction': ServiceRequestReports.get_customer_satisfaction_metrics(),
            'technician_performance': ServiceRequestReports.get_technician_performance_metrics(),
        }
        
        return success_response(data=analytics_data)
        
    except Exception as e:
        logger.error(f"Failed to get analytics: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to get analytics',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Task 10.2: Clarification Request Feature

@extend_schema(
    tags=['Service Requests - Admin'],
    summary='Request clarification from customer',
    description='Request additional information from customer',
    responses={200: RequestCommentSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_clarification(request, request_id):
    """
    Request clarification from customer.
    Task 10.2: Clarification request feature
    """
    # Only admin/manager can request clarification
    if request.user.role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can request clarification',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    clarification_message = request.data.get('message')
    if not clarification_message:
        return error_response(
            message='Clarification message is required',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from .clarifications import ClarificationManager
        
        comment = ClarificationManager.request_clarification(
            service_request=service_request,
            requested_by=request.user,
            clarification_message=clarification_message
        )
        
        return success_response(
            data=RequestCommentSerializer(comment, context={'request': request}).data,
            message='Clarification requested successfully'
        )
    except Exception as e:
        logger.error(f"Failed to request clarification: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to request clarification',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Service Requests'],
    summary='Respond to clarification request',
    description='Customer responds to clarification request',
    responses={200: RequestCommentSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_clarification(request, request_id):
    """
    Customer responds to clarification request.
    Task 10.2: Clarification request feature
    """
    try:
        service_request = ServiceRequest.objects.get(pk=request_id)
    except ServiceRequest.DoesNotExist:
        return error_response(
            message='Service request not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Only request owner can respond
    if service_request.customer != request.user:
        return error_response(
            message='You can only respond to clarifications for your own requests',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    response_message = request.data.get('message')
    if not response_message:
        return error_response(
            message='Response message is required',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        from .clarifications import ClarificationManager
        
        comment = ClarificationManager.respond_to_clarification(
            service_request=service_request,
            customer=request.user,
            response_message=response_message
        )
        
        return success_response(
            data=RequestCommentSerializer(comment, context={'request': request}).data,
            message='Response submitted successfully'
        )
    except Exception as e:
        logger.error(f"Failed to respond to clarification: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to respond to clarification',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
