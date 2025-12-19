"""
Files Views

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
import secrets

from .models import UserFile, FileShare
from .serializers import (
    UserFileSerializer, UploadFileSerializer, UpdateFileSerializer,
    AttachFileSerializer, FileShareSerializer, CreateFileShareSerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import ensure_tenant_role

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Attachments'],
    summary='List and upload files',
    description='Get paginated list of user files or upload a new file',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('file_type', str, description='Filter by file type'),
        OpenApiParameter('is_image', bool, description='Filter images only'),
        OpenApiParameter('is_attached', bool, description='Filter attached/unattached files'),
        OpenApiParameter('task_id', str, description='Filter by task'),
        OpenApiParameter('search', str, description='Search by filename or title'),
    ],
    request=UploadFileSerializer,
    responses={
        200: UserFileSerializer(many=True),
        201: UserFileSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def file_list_create(request):
    """
    List user's files or upload a new file.
    """
    if request.method == 'GET':
        # Get user's files
        queryset = UserFile.objects.filter(uploaded_by=request.user)
        
        # Apply filters
        file_type = request.query_params.get('file_type')
        if file_type:
            queryset = queryset.filter(file_type__icontains=file_type)
        
        is_image = request.query_params.get('is_image')
        if is_image is not None:
            queryset = queryset.filter(is_image=is_image.lower() == 'true')
        
        is_attached = request.query_params.get('is_attached')
        if is_attached is not None:
            if is_attached.lower() == 'true':
                queryset = queryset.filter(Q(task__isnull=False) | Q(service_request__isnull=False))
            else:
                queryset = queryset.filter(task__isnull=True, service_request__isnull=True)
        
        task_id = request.query_params.get('task_id')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        service_request_id = request.query_params.get('service_request_id')
        if service_request_id:
            queryset = queryset.filter(service_request_id=service_request_id)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(filename__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 20))
        paginator.max_page_size = 100
        
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = UserFileSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = UserFileSerializer(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        serializer = UploadFileSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid file data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                uploaded_file = serializer.validated_data['file']
                
                # Determine if file is an image
                is_image = uploaded_file.content_type.startswith('image/')
                
                # Create file record
                user_file = UserFile.objects.create(
                    file=uploaded_file,
                    filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type,
                    title=serializer.validated_data.get('title', ''),
                    description=serializer.validated_data.get('description', ''),
                    tags=serializer.validated_data.get('tags', []),
                    is_public=serializer.validated_data.get('is_public', False),
                    is_image=is_image,
                    uploaded_by=request.user
                )
                
                # Attach to task or service request if provided
                task_id = serializer.validated_data.get('task_id')
                if task_id:
                    from apps.tasks.models import Task
                    task = Task.objects.get(pk=task_id)
                    user_file.attach_to_task(task)
                
                service_request_id = serializer.validated_data.get('service_request_id')
                if service_request_id:
                    from apps.service_requests.models import ServiceRequest
                    service_request = ServiceRequest.objects.get(pk=service_request_id)
                    user_file.attach_to_service_request(service_request)
                
                logger.info(f"File uploaded: {user_file.filename} by {request.user.email}")
                
                return success_response(
                    data=UserFileSerializer(user_file, context={'request': request}).data,
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
    tags=['Attachments'],
    summary='Get, update, or delete file',
    description='Retrieve file details, update metadata, or delete file',
    request=UpdateFileSerializer,
    responses={200: UserFileSerializer}
)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def file_detail(request, file_id):
    """
    Retrieve, update, or delete a file.
    """
    try:
        user_file = UserFile.objects.get(pk=file_id)
    except UserFile.DoesNotExist:
        return error_response(
            message='File not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check ownership
    if user_file.uploaded_by != request.user:
        # Check if file is shared with user
        shared = FileShare.objects.filter(
            file=user_file,
            shared_with=request.user
        ).first()
        
        if not shared:
            return error_response(
                message='You do not have access to this file',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Check permissions for shared file
        if request.method in ['PATCH', 'DELETE'] and not shared.can_edit:
            return error_response(
                message='You do not have permission to modify this file',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    if request.method == 'GET':
        serializer = UserFileSerializer(user_file, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'PATCH':
        serializer = UpdateFileSerializer(user_file, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid file data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_file = serializer.save()
            logger.info(f"File updated: {user_file.filename} by {request.user.email}")
            
            return success_response(
                data=UserFileSerializer(user_file, context={'request': request}).data,
                message='File updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update file: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update file',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            filename = user_file.filename
            user_file.delete()
            
            logger.info(f"File deleted: {filename} by {request.user.email}")
            
            return success_response(message='File deleted successfully')
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete file',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Attachments'],
    summary='Attach file to entity',
    description='Attach file to a task or service request',
    request=AttachFileSerializer,
    responses={200: UserFileSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def attach_file(request, file_id):
    """
    Attach file to a task or service request.
    """
    try:
        user_file = UserFile.objects.get(pk=file_id, uploaded_by=request.user)
    except UserFile.DoesNotExist:
        return error_response(
            message='File not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = AttachFileSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        task_id = serializer.validated_data.get('task_id')
        service_request_id = serializer.validated_data.get('service_request_id')
        
        if task_id:
            from apps.tasks.models import Task
            task = Task.objects.get(pk=task_id)
            user_file.attach_to_task(task)
            message = f'File attached to task {task.task_number}'
        elif service_request_id:
            from apps.service_requests.models import ServiceRequest
            service_request = ServiceRequest.objects.get(pk=service_request_id)
            user_file.attach_to_service_request(service_request)
            message = f'File attached to service request {service_request.request_number}'
        
        logger.info(f"File attached: {user_file.filename} by {request.user.email}")
        
        return success_response(
            data=UserFileSerializer(user_file, context={'request': request}).data,
            message=message
        )
    except Exception as e:
        logger.error(f"Failed to attach file: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to attach file',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Attachments'],
    summary='Detach file from entity',
    description='Detach file from task or service request',
    responses={200: UserFileSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detach_file(request, file_id):
    """
    Detach file from all entities.
    """
    try:
        user_file = UserFile.objects.get(pk=file_id, uploaded_by=request.user)
    except UserFile.DoesNotExist:
        return error_response(
            message='File not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        user_file.detach()
        
        logger.info(f"File detached: {user_file.filename} by {request.user.email}")
        
        return success_response(
            data=UserFileSerializer(user_file, context={'request': request}).data,
            message='File detached successfully'
        )
    except Exception as e:
        logger.error(f"Failed to detach file: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to detach file',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# File Sharing Views

@extend_schema(
    tags=['Attachments - Sharing'],
    summary='List and create file shares',
    description='Get list of file shares or create a new share',
    request=CreateFileShareSerializer,
    responses={
        200: FileShareSerializer(many=True),
        201: FileShareSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def file_share_list_create(request):
    """
    List file shares or create a new share.
    """
    if request.method == 'GET':
        # Get shares created by user or shared with user
        queryset = FileShare.objects.filter(
            Q(shared_by=request.user) | Q(shared_with=request.user)
        )
        
        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get('page_size', 20))
        
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = FileShareSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = FileShareSerializer(queryset, many=True, context={'request': request})
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        serializer = CreateFileShareSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid share data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                file_id = serializer.validated_data['file_id']
                user_file = UserFile.objects.get(pk=file_id)
                
                # Check ownership
                if user_file.uploaded_by != request.user:
                    return error_response(
                        message='You can only share your own files',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
                
                # Create share
                share_data = {
                    'file': user_file,
                    'shared_by': request.user,
                    'can_download': serializer.validated_data.get('can_download', True),
                    'can_edit': serializer.validated_data.get('can_edit', False),
                    'expires_at': serializer.validated_data.get('expires_at'),
                }
                
                if serializer.validated_data.get('generate_public_link'):
                    # Generate public share token
                    share_data['share_token'] = secrets.token_urlsafe(32)
                else:
                    # Share with specific user
                    from apps.authentication.models import User
                    shared_with_id = serializer.validated_data['shared_with_id']
                    share_data['shared_with'] = User.objects.get(pk=shared_with_id)
                
                file_share = FileShare.objects.create(**share_data)
                
                logger.info(f"File shared: {user_file.filename} by {request.user.email}")
                
                return success_response(
                    data=FileShareSerializer(file_share, context={'request': request}).data,
                    message='File shared successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to share file: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to share file',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Attachments - Sharing'],
    summary='Delete file share',
    description='Revoke file share access',
    responses={200: {'description': 'Share deleted successfully'}}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def file_share_delete(request, share_id):
    """
    Delete a file share.
    """
    try:
        file_share = FileShare.objects.get(pk=share_id, shared_by=request.user)
    except FileShare.DoesNotExist:
        return error_response(
            message='Share not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        file_share.delete()
        
        logger.info(f"File share deleted by {request.user.email}")
        
        return success_response(message='Share deleted successfully')
    except Exception as e:
        logger.error(f"Failed to delete share: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to delete share',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Attachments - Sharing'],
    summary='Access shared file via public link',
    description='Access a file shared via public link (no authentication required)',
    responses={200: UserFileSerializer}
)
@api_view(['GET'])
@permission_classes([])  # Public endpoint
def shared_file_access(request, share_token):
    """
    Access a file via public share link.
    """
    try:
        file_share = FileShare.objects.get(share_token=share_token)
    except FileShare.DoesNotExist:
        return error_response(
            message='Invalid share link',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check if expired
    if file_share.is_expired:
        return error_response(
            message='Share link has expired',
            status_code=status.HTTP_410_GONE
        )
    
    # Record access
    file_share.record_access()
    
    # Return file details
    serializer = UserFileSerializer(file_share.file, context={'request': request})
    return success_response(
        data={
            'file': serializer.data,
            'can_download': file_share.can_download,
            'expires_at': file_share.expires_at,
        }
    )
