"""
Service Requests Signals

Task 9.2: Task status integration
Automatically update service request status when linked task status changes.

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from apps.tasks.models import Task
from .models import ServiceRequest, RequestAction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Task)
def update_request_on_task_status_change(sender, instance, created, **kwargs):
    """
    Update service request status when linked task status changes.
    
    Task Status -> Request Status mapping:
    - Task completed -> Request completed
    - Task closed -> Request completed
    - Task rejected -> Request accepted (revert to accepted)
    - Task reopened -> Request in_progress
    """
    if created:
        return  # Don't process on task creation
    
    try:
        # Find service request linked to this task
        service_request = ServiceRequest.objects.filter(converted_task=instance).first()
        
        if not service_request:
            return  # No linked service request
        
        # Track if status changed
        status_changed = False
        old_status = service_request.status
        
        # Update request status based on task status
        if instance.status == 'closed' and service_request.status != 'completed':
            service_request.mark_completed()
            status_changed = True
            
            # Log action
            RequestAction.log_action(
                request=service_request,
                action_type='completed',
                user=None,  # System action
                description=f'Request automatically completed when task {instance.task_number} was closed',
                metadata={
                    'task_id': str(instance.id),
                    'task_number': instance.task_number,
                    'task_status': instance.status,
                }
            )
            
            logger.info(
                f"Service request {service_request.request_number} marked completed "
                f"due to task {instance.task_number} closure"
            )
        
        elif instance.status == 'rejected' and service_request.status == 'in_progress':
            # Revert to accepted if task is rejected
            service_request.status = 'accepted'
            service_request.save()
            status_changed = True
            
            RequestAction.log_action(
                request=service_request,
                action_type='updated',
                user=None,
                description=f'Request reverted to accepted when task {instance.task_number} was rejected',
                metadata={
                    'task_id': str(instance.id),
                    'task_number': instance.task_number,
                    'task_status': instance.status,
                    'old_request_status': old_status,
                }
            )
            
            logger.info(
                f"Service request {service_request.request_number} reverted to accepted "
                f"due to task {instance.task_number} rejection"
            )
        
        elif instance.status == 'reopened' and service_request.status == 'completed':
            # Revert to in_progress if task is reopened
            service_request.status = 'in_progress'
            service_request.completed_at = None
            service_request.save()
            status_changed = True
            
            RequestAction.log_action(
                request=service_request,
                action_type='updated',
                user=None,
                description=f'Request reopened when task {instance.task_number} was reopened',
                metadata={
                    'task_id': str(instance.id),
                    'task_number': instance.task_number,
                    'task_status': instance.status,
                    'old_request_status': old_status,
                }
            )
            
            logger.info(
                f"Service request {service_request.request_number} reopened "
                f"due to task {instance.task_number} reopening"
            )
        
        # TODO: Send notification to customer if status changed
        
    except Exception as e:
        logger.error(
            f"Error updating service request on task status change: {str(e)}",
            exc_info=True
        )


@receiver(post_save, sender='tasks.TaskAssignment')
def notify_customer_on_technician_assignment(sender, instance, created, **kwargs):
    """
    Notify customer when technician is assigned to their service request's task.
    """
    if not created:
        return
    
    try:
        # Find service request linked to this task
        service_request = ServiceRequest.objects.filter(converted_task=instance.task).first()
        
        if not service_request:
            return
        
        # Log action
        RequestAction.log_action(
            request=service_request,
            action_type='updated',
            user=instance.assignee,
            description=f'Technician {instance.assignee.full_name} assigned to task {instance.task.task_number}',
            metadata={
                'task_id': str(instance.task.id),
                'task_number': instance.task.task_number,
                'technician_id': str(instance.assignee.id),
                'technician_name': instance.assignee.full_name,
            }
        )
        
        # TODO: Send notification to customer
        
        logger.info(
            f"Technician {instance.assignee.full_name} assigned to service request "
            f"{service_request.request_number} via task {instance.task.task_number}"
        )
        
    except Exception as e:
        logger.error(
            f"Error notifying customer on technician assignment: {str(e)}",
            exc_info=True
        )
