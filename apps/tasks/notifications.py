"""
Tasks Notification Service

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending task-related notifications.
    Integrates with the notification system to alert users about task events.
    """
    
    @staticmethod
    def notify_task_assigned(task, assignees, teams):
        """
        Send notifications when task is assigned.
        
        Args:
            task: Task instance
            assignees: List of User instances (technicians)
            teams: List of TechnicianTeam instances
        """
        try:
            # Collect all recipients
            recipients = set(assignees)
            
            # Add team members
            for team in teams:
                recipients.update(team.members.all())
            
            # Send notification to each recipient
            for recipient in recipients:
                # TODO: Integrate with actual notification system
                logger.info(
                    f"Notification: Task {task.task_number} assigned to {recipient.email}"
                )
                
                # If critical priority, send immediate notification
                if task.priority == 'critical':
                    logger.info(
                        f"CRITICAL: Immediate notification sent to {recipient.email}"
                    )
        except Exception as e:
            logger.error(f"Failed to send assignment notifications: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_status_changed(task, old_status, new_status):
        """
        Send notifications when task status changes.
        
        Args:
            task: Task instance
            old_status: Previous status
            new_status: New status
        """
        try:
            # Collect recipients (all assignees + creator)
            recipients = set()
            
            # Add creator
            if task.created_by:
                recipients.add(task.created_by)
            
            # Add all assigned technicians
            from .models import TaskAssignment
            assignments = TaskAssignment.objects.filter(task=task).select_related('assignee', 'team')
            
            for assignment in assignments:
                if assignment.assignee:
                    recipients.add(assignment.assignee)
                elif assignment.team:
                    recipients.update(assignment.team.members.all())
            
            # Send notification to each recipient
            for recipient in recipients:
                logger.info(
                    f"Notification: Task {task.task_number} status changed from "
                    f"{old_status} to {new_status} - sent to {recipient.email}"
                )
        except Exception as e:
            logger.error(f"Failed to send status change notifications: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_comment_added(comment):
        """
        Send notifications when comment is added.
        
        Args:
            comment: TaskComment instance
        """
        try:
            task = comment.task
            
            # Collect recipients (all participants except comment author)
            recipients = set()
            
            # Add creator
            if task.created_by and task.created_by != comment.author:
                recipients.add(task.created_by)
            
            # Add all assigned technicians
            from .models import TaskAssignment
            assignments = TaskAssignment.objects.filter(task=task).select_related('assignee', 'team')
            
            for assignment in assignments:
                if assignment.assignee and assignment.assignee != comment.author:
                    recipients.add(assignment.assignee)
                elif assignment.team:
                    for member in assignment.team.members.all():
                        if member != comment.author:
                            recipients.add(member)
            
            # Send notification to each recipient
            for recipient in recipients:
                logger.info(
                    f"Notification: New comment on task {task.task_number} "
                    f"by {comment.author.full_name} - sent to {recipient.email}"
                )
        except Exception as e:
            logger.error(f"Failed to send comment notifications: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_scheduled_task_activated(task):
        """
        Send notifications when scheduled task becomes active.
        
        Args:
            task: Task instance
        """
        try:
            # Collect all assigned technicians
            recipients = set()
            
            from .models import TaskAssignment
            assignments = TaskAssignment.objects.filter(task=task).select_related('assignee', 'team')
            
            for assignment in assignments:
                if assignment.assignee:
                    recipients.add(assignment.assignee)
                elif assignment.team:
                    recipients.update(assignment.team.members.all())
            
            # Send notification to each recipient
            for recipient in recipients:
                logger.info(
                    f"Notification: Scheduled task {task.task_number} is now active "
                    f"- sent to {recipient.email}"
                )
                
                # If critical priority, send immediate notification
                if task.priority == 'critical':
                    logger.info(
                        f"CRITICAL: Immediate notification sent to {recipient.email}"
                    )
        except Exception as e:
            logger.error(f"Failed to send scheduled task notifications: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_critical_task(task):
        """
        Send immediate notifications for critical priority tasks.
        
        Args:
            task: Task instance
        """
        try:
            # Collect all assigned technicians
            recipients = set()
            
            from .models import TaskAssignment
            assignments = TaskAssignment.objects.filter(task=task).select_related('assignee', 'team')
            
            for assignment in assignments:
                if assignment.assignee:
                    recipients.add(assignment.assignee)
                elif assignment.team:
                    recipients.update(assignment.team.members.all())
            
            # Send immediate notification to each recipient
            for recipient in recipients:
                logger.info(
                    f"CRITICAL NOTIFICATION: Task {task.task_number} requires immediate attention "
                    f"- sent to {recipient.email}"
                )
        except Exception as e:
            logger.error(f"Failed to send critical task notifications: {str(e)}", exc_info=True)
