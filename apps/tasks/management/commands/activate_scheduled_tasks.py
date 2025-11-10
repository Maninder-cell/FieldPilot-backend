"""
Management command to activate scheduled tasks.

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.tasks.models import Task
from apps.tasks.notifications import NotificationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Activate scheduled tasks that are due'

    def handle(self, *args, **options):
        """
        Find and activate scheduled tasks that are due.
        """
        now = timezone.now()
        
        # Find scheduled tasks that should be activated
        tasks_to_activate = Task.objects.filter(
            is_scheduled=True,
            scheduled_start__lte=now,
            status='new'
        )
        
        activated_count = 0
        
        for task in tasks_to_activate:
            try:
                # Update task to make it visible
                task.is_scheduled = False
                task.save(update_fields=['is_scheduled'])
                
                # Send notifications
                NotificationService.notify_scheduled_task_activated(task)
                
                activated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Activated task: {task.task_number}')
                )
                
                logger.info(f"Scheduled task activated: {task.task_number}")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to activate task {task.task_number}: {str(e)}')
                )
                logger.error(f"Failed to activate scheduled task: {str(e)}", exc_info=True)
        
        if activated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully activated {activated_count} scheduled task(s)')
            )
        else:
            self.stdout.write('No scheduled tasks to activate')
