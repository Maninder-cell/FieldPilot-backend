"""
Tasks Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
import logging

from .models import (
    Task, TechnicianTeam, TaskAssignment, TimeLog,
    TaskComment, TaskAttachment, TaskHistory, MaterialLog
)
from .notifications import NotificationService
from .serializers import (
    TaskSerializer, TaskListSerializer, CreateTaskSerializer, UpdateTaskSerializer,
    AssignTaskSerializer, UpdateTaskStatusSerializer, UpdateWorkStatusSerializer,
    TechnicianTeamSerializer, TechnicianTeamListSerializer,
    CreateTeamSerializer, UpdateTeamSerializer, AddTeamMembersSerializer,
    TimeLogSerializer, TravelLogSerializer, ArrivalLogSerializer,
    DepartureLogSerializer, LunchStartSerializer, LunchEndSerializer,
    TaskCommentSerializer, CreateCommentSerializer, UpdateCommentSerializer,
    TaskAttachmentSerializer, UploadAttachmentSerializer,
    MaterialLogSerializer, LogMaterialSerializer, TaskHistorySerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import IsAdminUser

logger = logging.getLogger(__name__)


# Task CRUD Endpoints

@extend_schema(
    tags=['Tasks'],
    summary='List and create tasks',
    description='Get paginated list of tasks with filtering and search, or create a new task',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('status', str, description='Filter by status'),
        OpenApiParameter('priority', str, description='Filter by priority'),
        OpenApiParameter('equipment', str, description='Filter by equipment ID'),
        OpenApiParameter('assignee', str, description='Filter by assignee ID'),
        OpenApiParameter('search', str, description='Search by title, description, or task number'),
    ],
    request=CreateTaskSerializer,
    responses={
        200: TaskListSerializer(many=True),
        201: TaskSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def task_list_create(request):
    """
    List tasks with pagination and filtering, or create a new task.
    """
    if request.method == 'GET':
        # Get queryset based on user role
        if request.tenant_role == 'technician':
            # Technicians see tasks assigned to them or their teams
            queryset = Task.objects.filter(
                Q(assignments__assignee=request.user) |
                Q(assignments__team__members=request.user)
            ).distinct()
            
            # Filter out scheduled tasks not yet visible
            queryset = queryset.filter(
                Q(is_scheduled=False) |
                Q(scheduled_start__lte=timezone.now())
            )
        else:
            # Admin/Manager see all tasks
            queryset = Task.objects.all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        equipment_filter = request.query_params.get('equipment')
        if equipment_filter:
            queryset = queryset.filter(equipment_id=equipment_filter)
        
        assignee_filter = request.query_params.get('assignee')
        if assignee_filter:
            queryset = queryset.filter(assignments__assignee_id=assignee_filter).distinct()
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(task_number__icontains=search)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = TaskListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Tasks retrieved successfully'
            })
        
        serializer = TaskListSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Tasks retrieved successfully'
        )
    
    elif request.method == 'POST':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can create tasks',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CreateTaskSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid task data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Create task
                task = Task.objects.create(
                    equipment=serializer.equipment,
                    title=serializer.validated_data['title'],
                    description=serializer.validated_data['description'],
                    priority=serializer.validated_data.get('priority', 'medium'),
                    status=serializer.validated_data.get('status', 'new'),
                    scheduled_start=serializer.validated_data.get('scheduled_start'),
                    scheduled_end=serializer.validated_data.get('scheduled_end'),
                    materials_needed=serializer.validated_data.get('materials_needed', []),
                    notes=serializer.validated_data.get('notes', ''),
                    custom_fields=serializer.validated_data.get('custom_fields', {}),
                    created_by=request.user
                )
                
                # Create assignments
                assignees = getattr(serializer, 'assignees', [])
                for assignee in assignees:
                    TaskAssignment.objects.create(
                        task=task,
                        assignee=assignee,
                        assigned_by=request.user
                    )
                
                teams = getattr(serializer, 'teams', [])
                for team in teams:
                    TaskAssignment.objects.create(
                        task=task,
                        team=team,
                        assigned_by=request.user
                    )
                
                # Log history
                TaskHistory.log_action(
                    task=task,
                    action='created',
                    user=request.user,
                    details={
                        'priority': task.priority,
                        'status': task.status,
                        'assignee_count': len(assignees),
                        'team_count': len(teams)
                    }
                )
                
                # Send notifications
                NotificationService.notify_task_assigned(task, assignees, teams)
                
                # Send critical notification if priority is critical
                if task.priority == 'critical':
                    NotificationService.notify_critical_task(task)
                
                logger.info(f"Task created: {task.task_number} by {request.user.email}")
                
                return success_response(
                    data=TaskSerializer(task).data,
                    message='Task created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create task: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create task',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Tasks'],
    summary='Get, update, or delete task',
    description='Retrieve task details, update task information, or soft delete a task',
    request=UpdateTaskSerializer,
    responses={
        200: TaskSerializer,
        404: {'description': 'Task not found'},
    }
)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def task_detail(request, task_id):
    """
    Retrieve, update, or delete a task.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        # Technicians can only access tasks assigned to them
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    if request.method == 'GET':
        serializer = TaskSerializer(task)
        return success_response(
            data=serializer.data,
            message='Task retrieved successfully'
        )
    
    elif request.method == 'PATCH':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can update tasks',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = UpdateTaskSerializer(task, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid task data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Track changes for history
                changes = {}
                for field in serializer.validated_data:
                    old_value = getattr(task, field)
                    new_value = serializer.validated_data[field]
                    if old_value != new_value:
                        changes[field] = {'old': old_value, 'new': new_value}
                
                task = serializer.save(updated_by=request.user)
                
                # Log history for each change
                for field, values in changes.items():
                    TaskHistory.log_action(
                        task=task,
                        action='status_changed' if field == 'status' else 'updated',
                        user=request.user,
                        field_name=field,
                        old_value=str(values['old']),
                        new_value=str(values['new'])
                    )
                
                # Reset work status if reopened
                if 'status' in changes and changes['status']['new'] == 'reopened':
                    TaskAssignment.objects.filter(task=task).update(work_status='open')
                
                logger.info(f"Task updated: {task.task_number} by {request.user.email}")
                
                return success_response(
                    data=TaskSerializer(task).data,
                    message='Task updated successfully'
                )
        except Exception as e:
            logger.error(f"Failed to update task: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update task',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can delete tasks',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Soft delete
            task.delete()
            
            logger.info(f"Task deleted: {task.task_number} by {request.user.email}")
            
            return success_response(
                message='Task deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete task: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete task',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# Task Assignment and Status Endpoints

@extend_schema(
    tags=['Tasks'],
    summary='Assign task to technicians or teams',
    description='Assign a task to one or more technicians or teams',
    request=AssignTaskSerializer,
    responses={200: TaskSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_assign(request, task_id):
    """
    Assign task to technicians or teams.
    """
    # Check permissions (admin/manager only)
    if request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can assign tasks',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = AssignTaskSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid assignment data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create assignments
            assignees = getattr(serializer, 'assignees', [])
            for assignee in assignees:
                TaskAssignment.objects.get_or_create(
                    task=task,
                    assignee=assignee,
                    defaults={'assigned_by': request.user}
                )
            
            teams = getattr(serializer, 'teams', [])
            for team in teams:
                TaskAssignment.objects.get_or_create(
                    task=task,
                    team=team,
                    defaults={'assigned_by': request.user}
                )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='assigned',
                user=request.user,
                details={
                    'assignee_count': len(assignees),
                    'team_count': len(teams)
                }
            )
            
            # Send notifications
            NotificationService.notify_task_assigned(task, assignees, teams)
            
            logger.info(f"Task assigned: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TaskSerializer(task).data,
                message='Task assigned successfully'
            )
    except Exception as e:
        logger.error(f"Failed to assign task: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to assign task',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Tasks'],
    summary='Update task status',
    description='Update administrative status of a task (admin/manager only)',
    request=UpdateTaskStatusSerializer,
    responses={200: TaskSerializer}
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def task_update_status(request, task_id):
    """
    Update task administrative status.
    """
    # Check permissions (admin/manager only)
    if request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can update task status',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = UpdateTaskStatusSerializer(data=request.data, context={'task': task})
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid status data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            old_status = task.status
            new_status = serializer.validated_data['status']
            
            task.status = new_status
            task.updated_by = request.user
            task.save()
            
            # Reset work status if reopened
            if new_status == 'reopened':
                TaskAssignment.objects.filter(task=task).update(work_status='open')
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='status_changed',
                user=request.user,
                field_name='status',
                old_value=old_status,
                new_value=new_status
            )
            
            # Send notifications
            NotificationService.notify_status_changed(task, old_status, new_status)
            
            logger.info(f"Task status updated: {task.task_number} from {old_status} to {new_status}")
            
            return success_response(
                data=TaskSerializer(task).data,
                message='Task status updated successfully'
            )
    except Exception as e:
        logger.error(f"Failed to update task status: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to update task status',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Tasks'],
    summary='Update work status',
    description='Update work status of a task assignment (technician only)',
    request=UpdateWorkStatusSerializer,
    responses={200: TaskSerializer}
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def task_update_work_status(request, task_id):
    """
    Update work status for technician's assignment.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can update work status',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Get technician's assignment
    try:
        assignment = TaskAssignment.objects.get(
            task=task,
            assignee=request.user
        )
    except TaskAssignment.DoesNotExist:
        return error_response(
            message='You are not assigned to this task',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    serializer = UpdateWorkStatusSerializer(
        data=request.data,
        context={'assignment': assignment}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid work status data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            old_work_status = assignment.work_status
            new_work_status = serializer.validated_data['work_status']
            
            assignment.work_status = new_work_status
            assignment.save()
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='work_status_changed',
                user=request.user,
                field_name='work_status',
                old_value=old_work_status,
                new_value=new_work_status,
                details={'assignee': request.user.full_name}
            )
            
            logger.info(f"Work status updated: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TaskSerializer(task).data,
                message='Work status updated successfully'
            )
    except Exception as e:
        logger.error(f"Failed to update work status: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to update work status',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Tasks'],
    summary='Get task history',
    description='Retrieve complete audit trail for a task',
    parameters=[
        OpenApiParameter('action', str, description='Filter by action type'),
        OpenApiParameter('user', str, description='Filter by user ID'),
    ],
    responses={200: TaskHistorySerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_history(request, task_id):
    """
    Get task history (audit trail).
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    # Get history
    history = TaskHistory.objects.filter(task=task)
    
    # Apply filters
    action_filter = request.query_params.get('action')
    if action_filter:
        history = history.filter(action=action_filter)
    
    user_filter = request.query_params.get('user')
    if user_filter:
        history = history.filter(user_id=user_filter)
    
    # Order by created_at descending
    history = history.order_by('-created_at')
    
    serializer = TaskHistorySerializer(history, many=True)
    return success_response(
        data=serializer.data,
        message='Task history retrieved successfully'
    )



# Team Management Endpoints

@extend_schema(
    tags=['Teams'],
    summary='List and create teams',
    description='Get paginated list of teams or create a new team',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('is_active', bool, description='Filter by active status'),
        OpenApiParameter('search', str, description='Search by team name'),
    ],
    request=CreateTeamSerializer,
    responses={
        200: TechnicianTeamListSerializer(many=True),
        201: TechnicianTeamSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def team_list_create(request):
    """
    List teams with pagination and filtering, or create a new team.
    """
    if request.method == 'GET':
        queryset = TechnicianTeam.objects.all()
        
        # Apply filters
        is_active_filter = request.query_params.get('is_active')
        if is_active_filter is not None:
            is_active = is_active_filter.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        # Apply search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Order by name
        queryset = queryset.order_by('name')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = TechnicianTeamListSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Teams retrieved successfully'
            })
        
        serializer = TechnicianTeamListSerializer(queryset, many=True)
        return success_response(
            data=serializer.data,
            message='Teams retrieved successfully'
        )
    
    elif request.method == 'POST':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can create teams',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CreateTeamSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid team data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Create team
                team = TechnicianTeam.objects.create(
                    name=serializer.validated_data['name'],
                    description=serializer.validated_data.get('description', ''),
                    is_active=serializer.validated_data.get('is_active', True),
                    created_by=request.user
                )
                
                # Add members
                members = getattr(serializer, 'members', [])
                if members:
                    team.members.set(members)
                
                logger.info(f"Team created: {team.name} by {request.user.email}")
                
                return success_response(
                    data=TechnicianTeamSerializer(team).data,
                    message='Team created successfully',
                    status_code=status.HTTP_201_CREATED
                )
        except Exception as e:
            logger.error(f"Failed to create team: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to create team',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Teams'],
    summary='Get, update, or delete team',
    description='Retrieve team details, update team information, or soft delete a team',
    request=UpdateTeamSerializer,
    responses={
        200: TechnicianTeamSerializer,
        404: {'description': 'Team not found'},
    }
)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def team_detail(request, team_id):
    """
    Retrieve, update, or delete a team.
    """
    try:
        team = TechnicianTeam.objects.get(pk=team_id)
    except TechnicianTeam.DoesNotExist:
        return error_response(
            message='Team not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = TechnicianTeamSerializer(team)
        return success_response(
            data=serializer.data,
            message='Team retrieved successfully'
        )
    
    elif request.method == 'PATCH':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can update teams',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        serializer = UpdateTeamSerializer(team, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid team data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            team = serializer.save(updated_by=request.user)
            
            logger.info(f"Team updated: {team.name} by {request.user.email}")
            
            return success_response(
                data=TechnicianTeamSerializer(team).data,
                message='Team updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update team: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update team',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        # Check permissions (admin/manager only)
        if request.tenant_role not in ['admin', 'manager']:
            return error_response(
                message='Only admins and managers can delete teams',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Soft delete
            team.delete()
            
            logger.info(f"Team deleted: {team.name} by {request.user.email}")
            
            return success_response(
                message='Team deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete team: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete team',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Teams'],
    summary='Add team members',
    description='Add members to a team',
    request=AddTeamMembersSerializer,
    responses={200: TechnicianTeamSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def team_add_members(request, team_id):
    """
    Add members to a team.
    """
    # Check permissions (admin/manager only)
    if request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can add team members',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        team = TechnicianTeam.objects.get(pk=team_id)
    except TechnicianTeam.DoesNotExist:
        return error_response(
            message='Team not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = AddTeamMembersSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid member data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        members = getattr(serializer, 'members', [])
        team.members.add(*members)
        
        logger.info(f"Members added to team: {team.name} by {request.user.email}")
        
        return success_response(
            data=TechnicianTeamSerializer(team).data,
            message='Members added successfully'
        )
    except Exception as e:
        logger.error(f"Failed to add members: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to add members',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Teams'],
    summary='Remove team member',
    description='Remove a member from a team',
    responses={200: TechnicianTeamSerializer}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def team_remove_member(request, team_id, member_id):
    """
    Remove a member from a team.
    """
    # Check permissions (admin/manager only)
    if request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='Only admins and managers can remove team members',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        team = TechnicianTeam.objects.get(pk=team_id)
    except TechnicianTeam.DoesNotExist:
        return error_response(
            message='Team not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    try:
        from apps.authentication.models import User
        member = User.objects.get(pk=member_id)
        
        if member not in team.members.all():
            return error_response(
                message='Member not in team',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        team.members.remove(member)
        
        logger.info(f"Member removed from team: {team.name} by {request.user.email}")
        
        return success_response(
            data=TechnicianTeamSerializer(team).data,
            message='Member removed successfully'
        )
    except User.DoesNotExist:
        return error_response(
            message='Member not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to remove member: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to remove member',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# Time Tracking Endpoints

@extend_schema(
    tags=['Time Tracking'],
    summary='Log travel started',
    description='Log that technician started traveling to site',
    request=TravelLogSerializer,
    responses={200: TimeLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_travel(request, task_id):
    """
    Log travel started for a task.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can log travel',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check if assigned
    is_assigned = TaskAssignment.objects.filter(
        Q(task=task, assignee=request.user) |
        Q(task=task, team__members=request.user)
    ).exists()
    
    if not is_assigned:
        return error_response(
            message='You are not assigned to this task',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TravelLogSerializer(
        data=request.data,
        context={'task': task, 'technician': request.user}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Cannot start travel',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Get active time log or create new one
            time_log, created = TimeLog.get_or_create_active_log(
                task=task,
                technician=request.user
            )
            
            # Check if travel already started for this visit
            if time_log.travel_started_at:
                return error_response(
                    message='Travel already started for this visit. Complete the current visit before starting a new one.',
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Set travel start time
            time_log.travel_started_at = timezone.now()
            time_log.save(update_fields=['travel_started_at', 'updated_at'])
            
            # Add system comment
            TaskComment.create_system_comment(
                task=task,
                comment_text=f"{request.user.full_name} started traveling to site at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='travel_started',
                user=request.user,
                details={'time': timezone.now().isoformat()}
            )
            
            logger.info(f"Travel started: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TimeLogSerializer(time_log).data,
                message='Travel started successfully'
            )
    except Exception as e:
        logger.error(f"Failed to log travel: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log travel',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Time Tracking'],
    summary='Log arrival at site',
    description='Log that technician arrived at site',
    request=ArrivalLogSerializer,
    responses={200: TimeLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_arrive(request, task_id):
    """
    Log arrival at site for a task.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can log arrival',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Get active time log
    time_log = TimeLog.get_active_log(task=task, technician=request.user)
    if not time_log:
        return error_response(
            message='No active time log found. Start travel first.',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = ArrivalLogSerializer(
        data=request.data,
        context={'time_log': time_log}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Cannot log arrival',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            time_log.arrived_at = timezone.now()
            time_log.save()
            
            # Add system comment
            TaskComment.create_system_comment(
                task=task,
                comment_text=f"{request.user.full_name} arrived at site at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='arrived',
                user=request.user,
                details={'time': timezone.now().isoformat()}
            )
            
            logger.info(f"Arrival logged: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TimeLogSerializer(time_log).data,
                message='Arrival logged successfully'
            )
    except Exception as e:
        logger.error(f"Failed to log arrival: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log arrival',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Time Tracking'],
    summary='Log departure from site',
    description='Log that technician departed from site with equipment status',
    request=DepartureLogSerializer,
    responses={200: TimeLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_depart(request, task_id):
    """
    Log departure from site for a task.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can log departure',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Get active time log
    time_log = TimeLog.get_active_log(task=task, technician=request.user)
    if not time_log:
        return error_response(
            message='No active time log found',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = DepartureLogSerializer(
        data=request.data,
        context={'time_log': time_log}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Cannot log departure',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            time_log.departed_at = timezone.now()
            time_log.equipment_status_at_departure = serializer.validated_data['equipment_status']
            time_log.calculate_work_hours()
            time_log.save()
            
            # Add system comment
            TaskComment.create_system_comment(
                task=task,
                comment_text=f"{request.user.full_name} departed from site at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}. "
                            f"Equipment status: {time_log.get_equipment_status_at_departure_display()}. "
                            f"Work hours: {time_log.total_work_hours}h (Normal: {time_log.normal_hours}h, Overtime: {time_log.overtime_hours}h)"
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='departed',
                user=request.user,
                details={
                    'time': timezone.now().isoformat(),
                    'equipment_status': time_log.equipment_status_at_departure,
                    'work_hours': float(time_log.total_work_hours)
                }
            )
            
            logger.info(f"Departure logged: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TimeLogSerializer(time_log).data,
                message='Departure logged successfully'
            )
    except Exception as e:
        logger.error(f"Failed to log departure: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log departure',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Time Tracking'],
    summary='Log lunch start',
    description='Log that technician started lunch break',
    request=LunchStartSerializer,
    responses={200: TimeLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_lunch_start(request, task_id):
    """
    Log lunch break start for a task.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can log lunch',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Get active time log
    time_log = TimeLog.get_active_log(task=task, technician=request.user)
    if not time_log:
        return error_response(
            message='No active time log found',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = LunchStartSerializer(
        data=request.data,
        context={'time_log': time_log}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Cannot start lunch',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            time_log.lunch_started_at = timezone.now()
            time_log.save()
            
            # Add system comment
            TaskComment.create_system_comment(
                task=task,
                comment_text=f"{request.user.full_name} started lunch break at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='lunch_started',
                user=request.user,
                details={'time': timezone.now().isoformat()}
            )
            
            logger.info(f"Lunch started: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TimeLogSerializer(time_log).data,
                message='Lunch break started successfully'
            )
    except Exception as e:
        logger.error(f"Failed to log lunch start: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log lunch start',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Time Tracking'],
    summary='Log lunch end',
    description='Log that technician ended lunch break',
    request=LunchEndSerializer,
    responses={200: TimeLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_lunch_end(request, task_id):
    """
    Log lunch break end for a task.
    """
    # Check permissions (technician only)
    if request.tenant_role != 'technician':
        return error_response(
            message='Only technicians can log lunch',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Get active time log
    time_log = TimeLog.get_active_log(task=task, technician=request.user)
    if not time_log:
        return error_response(
            message='No active time log found',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = LunchEndSerializer(
        data=request.data,
        context={'time_log': time_log}
    )
    
    if not serializer.is_valid():
        return error_response(
            message='Cannot end lunch',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            time_log.lunch_ended_at = timezone.now()
            time_log.save()
            
            # Calculate lunch duration
            lunch_duration = time_log.lunch_ended_at - time_log.lunch_started_at
            lunch_minutes = int(lunch_duration.total_seconds() / 60)
            
            # Add system comment
            TaskComment.create_system_comment(
                task=task,
                comment_text=f"{request.user.full_name} ended lunch break at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} "
                            f"(Duration: {lunch_minutes} minutes)"
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='lunch_ended',
                user=request.user,
                details={
                    'time': timezone.now().isoformat(),
                    'duration_minutes': lunch_minutes
                }
            )
            
            logger.info(f"Lunch ended: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=TimeLogSerializer(time_log).data,
                message='Lunch break ended successfully'
            )
    except Exception as e:
        logger.error(f"Failed to log lunch end: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log lunch end',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Time Tracking'],
    summary='Get time logs for task',
    description='Retrieve all time logs for a task',
    responses={200: TimeLogSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_time_logs(request, task_id):
    """
    Get time logs for a task.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    time_logs = TimeLog.objects.filter(task=task).order_by('-created_at')
    serializer = TimeLogSerializer(time_logs, many=True)
    
    return success_response(
        data=serializer.data,
        message='Time logs retrieved successfully'
    )



# Comment Endpoints

@extend_schema(
    tags=['Comments'],
    summary='List and create comments',
    description='Get comments for a task or add a new comment',
    request=CreateCommentSerializer,
    responses={
        200: TaskCommentSerializer(many=True),
        201: TaskCommentSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def task_comments(request, task_id):
    """
    List comments for a task or create a new comment.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    if request.method == 'GET':
        comments = TaskComment.objects.filter(task=task).order_by('created_at')
        
        # Paginate
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(comments, request)
        
        if page is not None:
            serializer = TaskCommentSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Comments retrieved successfully'
            })
        
        serializer = TaskCommentSerializer(comments, many=True)
        return success_response(
            data=serializer.data,
            message='Comments retrieved successfully'
        )
    
    elif request.method == 'POST':
        serializer = CreateCommentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid comment data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                comment = TaskComment.objects.create(
                    task=task,
                    author=request.user,
                    comment=serializer.validated_data['comment']
                )
                
                # Log history
                TaskHistory.log_action(
                    task=task,
                    action='comment_added',
                    user=request.user,
                    details={'comment_id': str(comment.id)}
                )
                
                # Send notifications
                NotificationService.notify_comment_added(comment)
                
                logger.info(f"Comment added: {task.task_number} by {request.user.email}")
                
                return success_response(
                    data=TaskCommentSerializer(comment).data,
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
    tags=['Comments'],
    summary='Update or delete comment',
    description='Update or delete a comment',
    request=UpdateCommentSerializer,
    responses={200: TaskCommentSerializer}
)
@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def comment_detail(request, comment_id):
    """
    Update or delete a comment.
    """
    try:
        comment = TaskComment.objects.get(pk=comment_id)
    except TaskComment.DoesNotExist:
        return error_response(
            message='Comment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions (only author can update/delete)
    if comment.author != request.user and request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='You can only modify your own comments',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'PATCH':
        serializer = UpdateCommentSerializer(comment, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid comment data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            comment = serializer.save()
            
            logger.info(f"Comment updated: {comment.id} by {request.user.email}")
            
            return success_response(
                data=TaskCommentSerializer(comment).data,
                message='Comment updated successfully'
            )
        except Exception as e:
            logger.error(f"Failed to update comment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to update comment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        try:
            comment.delete()
            
            logger.info(f"Comment deleted: {comment.id} by {request.user.email}")
            
            return success_response(
                message='Comment deleted successfully'
            )
        except Exception as e:
            logger.error(f"Failed to delete comment: {str(e)}", exc_info=True)
            return error_response(
                message='Failed to delete comment',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Attachment Endpoints

@extend_schema(
    tags=['Attachments'],
    summary='List and upload attachments',
    description='Get attachments for a task or upload a new file',
    request=UploadAttachmentSerializer,
    responses={
        200: TaskAttachmentSerializer(many=True),
        201: TaskAttachmentSerializer,
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def task_attachments(request, task_id):
    """
    List attachments for a task or upload a new file.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    if request.method == 'GET':
        attachments = TaskAttachment.objects.filter(task=task).order_by('-created_at')
        serializer = TaskAttachmentSerializer(attachments, many=True, context={'request': request})
        
        return success_response(
            data=serializer.data,
            message='Attachments retrieved successfully'
        )
    
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
                
                attachment = TaskAttachment.objects.create(
                    task=task,
                    uploaded_by=request.user,
                    file=uploaded_file,
                    filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type
                )
                
                # Log history
                TaskHistory.log_action(
                    task=task,
                    action='file_uploaded',
                    user=request.user,
                    details={
                        'filename': attachment.filename,
                        'file_size': attachment.file_size,
                        'file_type': attachment.file_type
                    }
                )
                
                logger.info(f"File uploaded: {task.task_number} by {request.user.email}")
                
                return success_response(
                    data=TaskAttachmentSerializer(attachment, context={'request': request}).data,
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
    summary='Delete attachment',
    description='Delete a file attachment',
    responses={200: {'description': 'Attachment deleted'}}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def attachment_delete(request, attachment_id):
    """
    Delete an attachment.
    """
    try:
        attachment = TaskAttachment.objects.get(pk=attachment_id)
    except TaskAttachment.DoesNotExist:
        return error_response(
            message='Attachment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check permissions (only uploader or admin/manager can delete)
    if attachment.uploaded_by != request.user and request.tenant_role not in ['admin', 'manager']:
        return error_response(
            message='You can only delete your own attachments',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Delete file from storage without saving the model
        if attachment.file:
            attachment.file.delete(save=False)
        
        # Delete the database record
        attachment.delete()
        
        logger.info(f"Attachment deleted: {attachment.id} by {request.user.email}")
        
        return success_response(
            message='Attachment deleted successfully'
        )
    except Exception as e:
        logger.error(f"Failed to delete attachment: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to delete attachment',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Attachments'],
    summary='Download attachment',
    description='Download a file attachment',
    responses={200: {'description': 'File download'}}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attachment_download(request, attachment_id):
    """
    Download an attachment.
    """
    try:
        attachment = TaskAttachment.objects.get(pk=attachment_id)
    except TaskAttachment.DoesNotExist:
        return error_response(
            message='Attachment not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    task = attachment.task
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    try:
        from django.http import FileResponse
        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=attachment.filename
        )
    except Exception as e:
        logger.error(f"Failed to download attachment: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to download attachment',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Material Tracking Endpoints

@extend_schema(
    tags=['Materials'],
    summary='Log materials needed',
    description='Log materials needed for a task',
    request=LogMaterialSerializer,
    responses={201: MaterialLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_materials_needed(request, task_id):
    """
    Log materials needed for a task.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = LogMaterialSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid material data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            material_log = MaterialLog.objects.create(
                task=task,
                log_type='needed',
                material_name=serializer.validated_data['material_name'],
                quantity=serializer.validated_data['quantity'],
                unit=serializer.validated_data['unit'],
                notes=serializer.validated_data.get('notes', ''),
                logged_by=request.user
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='material_needed',
                user=request.user,
                details={
                    'material': material_log.material_name,
                    'quantity': float(material_log.quantity),
                    'unit': material_log.unit
                }
            )
            
            logger.info(f"Material needed logged: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=MaterialLogSerializer(material_log).data,
                message='Material needed logged successfully',
                status_code=status.HTTP_201_CREATED
            )
    except Exception as e:
        logger.error(f"Failed to log material needed: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log material needed',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Materials'],
    summary='Log materials received',
    description='Log materials received for a task',
    request=LogMaterialSerializer,
    responses={201: MaterialLogSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def task_materials_received(request, task_id):
    """
    Log materials received for a task.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    serializer = LogMaterialSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid material data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            material_log = MaterialLog.objects.create(
                task=task,
                log_type='received',
                material_name=serializer.validated_data['material_name'],
                quantity=serializer.validated_data['quantity'],
                unit=serializer.validated_data['unit'],
                notes=serializer.validated_data.get('notes', ''),
                logged_by=request.user
            )
            
            # Log history
            TaskHistory.log_action(
                task=task,
                action='material_received',
                user=request.user,
                details={
                    'material': material_log.material_name,
                    'quantity': float(material_log.quantity),
                    'unit': material_log.unit
                }
            )
            
            logger.info(f"Material received logged: {task.task_number} by {request.user.email}")
            
            return success_response(
                data=MaterialLogSerializer(material_log).data,
                message='Material received logged successfully',
                status_code=status.HTTP_201_CREATED
            )
    except Exception as e:
        logger.error(f"Failed to log material received: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to log material received',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Materials'],
    summary='Get material logs',
    description='Retrieve all material logs for a task',
    parameters=[
        OpenApiParameter('log_type', str, description='Filter by log type (needed/received)'),
    ],
    responses={200: MaterialLogSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_materials(request, task_id):
    """
    Get material logs for a task.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return error_response(
            message='Task not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Check access permissions
    if request.tenant_role == 'technician':
        is_assigned = TaskAssignment.objects.filter(
            Q(task=task, assignee=request.user) |
            Q(task=task, team__members=request.user)
        ).exists()
        
        if not is_assigned:
            return error_response(
                message='You do not have access to this task',
                status_code=status.HTTP_403_FORBIDDEN
            )
    
    material_logs = MaterialLog.objects.filter(task=task)
    
    # Apply filter
    log_type_filter = request.query_params.get('log_type')
    if log_type_filter:
        material_logs = material_logs.filter(log_type=log_type_filter)
    
    material_logs = material_logs.order_by('-logged_at')
    serializer = MaterialLogSerializer(material_logs, many=True)
    
    return success_response(
        data=serializer.data,
        message='Material logs retrieved successfully'
    )



# Work Hours Reporting Endpoint

@extend_schema(
    tags=['Reports'],
    summary='Get work hours report',
    description='Aggregate work hours by technician and date range',
    parameters=[
        OpenApiParameter('technician', str, description='Filter by technician ID'),
        OpenApiParameter('start_date', str, description='Start date (YYYY-MM-DD)'),
        OpenApiParameter('end_date', str, description='End date (YYYY-MM-DD)'),
    ],
    responses={200: {'description': 'Work hours report'}}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def work_hours_report(request):
    """
    Get aggregated work hours report.
    """
    from datetime import datetime
    from .utils import WorkHoursCalculator
    
    # Check permissions (admin/manager can see all, technicians see only their own)
    if request.tenant_role == 'technician':
        technician_id = str(request.user.id)
    else:
        technician_id = request.query_params.get('technician')
    
    if not technician_id:
        return error_response(
            message='Technician ID is required',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Get technician
    try:
        from apps.authentication.models import User
        technician = User.objects.get(pk=technician_id, role='technician')
    except User.DoesNotExist:
        return error_response(
            message='Technician not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    # Parse dates
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return error_response(
            message='Invalid date format. Use YYYY-MM-DD',
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Get aggregated hours
    hours_data = WorkHoursCalculator.aggregate_hours_by_technician(
        technician=technician,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get detailed time logs
    time_logs = TimeLog.objects.filter(
        technician=technician,
        departed_at__isnull=False
    )
    
    if start_date:
        time_logs = time_logs.filter(departed_at__gte=start_date)
    if end_date:
        time_logs = time_logs.filter(departed_at__lte=end_date)
    
    time_logs = time_logs.order_by('-departed_at')
    
    data = {
        'technician': {
            'id': str(technician.id),
            'name': technician.full_name,
            'email': technician.email
        },
        'summary': hours_data,
        'time_logs': TimeLogSerializer(time_logs, many=True).data
    }
    
    return success_response(
        data=data,
        message='Work hours report retrieved successfully'
    )
