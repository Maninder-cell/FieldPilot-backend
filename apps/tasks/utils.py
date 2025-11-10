"""
Tasks Utilities - Business Logic Validators and Calculators

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.exceptions import ValidationError
from .models import TimeLog, TaskAssignment


class SiteConflictValidator:
    """
    Validates that technicians are not at multiple sites simultaneously.
    Prevents conflicts in time tracking and ensures accurate work hour calculation.
    """
    
    @staticmethod
    def can_travel(technician, task=None):
        """
        Check if technician can travel to a new site.
        
        Args:
            technician: User instance (technician)
            task: Task instance to exclude from check (optional)
        
        Returns:
            tuple: (can_travel: bool, error_message: str or None)
        """
        query = TimeLog.objects.filter(
            technician=technician,
            departed_at__isnull=True
        )
        
        if task:
            query = query.exclude(task=task)
        
        active_log = query.first()
        
        if active_log:
            return False, f"Technician is already at site for task {active_log.task.task_number}"
        
        return True, None
    
    @staticmethod
    def validate_travel(technician, task=None):
        """
        Validate that technician can travel (raises ValidationError if not).
        
        Args:
            technician: User instance (technician)
            task: Task instance to exclude from check (optional)
        
        Raises:
            ValidationError: If technician cannot travel
        """
        can_travel, error_message = SiteConflictValidator.can_travel(technician, task)
        if not can_travel:
            raise ValidationError(error_message)
    
    @staticmethod
    def get_active_site(technician):
        """
        Get the task where technician is currently active (if any).
        
        Args:
            technician: User instance (technician)
        
        Returns:
            TimeLog instance or None
        """
        return TimeLog.objects.filter(
            technician=technician,
            departed_at__isnull=True
        ).first()


class WorkHoursCalculator:
    """
    Calculates work hours, normal hours, and overtime for time logs.
    Normal hours are up to 8 hours per day, anything beyond is overtime.
    """
    
    NORMAL_HOURS_PER_DAY = 8
    
    @staticmethod
    def calculate(time_log):
        """
        Calculate work hours from time log.
        
        Args:
            time_log: TimeLog instance
        
        Returns:
            tuple: (total_hours: float, normal_hours: float, overtime_hours: float)
        """
        if not time_log.arrived_at or not time_log.departed_at:
            return 0, 0, 0
        
        # Calculate total time
        total_time = time_log.departed_at - time_log.arrived_at
        
        # Subtract lunch break if applicable
        if time_log.lunch_started_at and time_log.lunch_ended_at:
            lunch_duration = time_log.lunch_ended_at - time_log.lunch_started_at
            total_time -= lunch_duration
        
        # Convert to hours
        total_hours = total_time.total_seconds() / 3600
        
        # Calculate normal vs overtime
        normal_hours = min(total_hours, WorkHoursCalculator.NORMAL_HOURS_PER_DAY)
        overtime_hours = max(0, total_hours - WorkHoursCalculator.NORMAL_HOURS_PER_DAY)
        
        return (
            round(total_hours, 2),
            round(normal_hours, 2),
            round(overtime_hours, 2)
        )
    
    @staticmethod
    def calculate_and_update(time_log):
        """
        Calculate work hours and update the time log instance.
        
        Args:
            time_log: TimeLog instance
        
        Returns:
            TimeLog instance with updated hours
        """
        total_hours, normal_hours, overtime_hours = WorkHoursCalculator.calculate(time_log)
        
        time_log.total_work_hours = total_hours
        time_log.normal_hours = normal_hours
        time_log.overtime_hours = overtime_hours
        
        return time_log
    
    @staticmethod
    def aggregate_hours_by_technician(technician, start_date=None, end_date=None):
        """
        Aggregate work hours for a technician over a date range.
        
        Args:
            technician: User instance (technician)
            start_date: Start date for aggregation (optional)
            end_date: End date for aggregation (optional)
        
        Returns:
            dict: {
                'total_hours': float,
                'normal_hours': float,
                'overtime_hours': float,
                'task_count': int
            }
        """
        from django.db.models import Sum
        
        query = TimeLog.objects.filter(
            technician=technician,
            departed_at__isnull=False
        )
        
        if start_date:
            query = query.filter(departed_at__gte=start_date)
        if end_date:
            query = query.filter(departed_at__lte=end_date)
        
        aggregates = query.aggregate(
            total_hours=Sum('total_work_hours'),
            normal_hours=Sum('normal_hours'),
            overtime_hours=Sum('overtime_hours')
        )
        
        return {
            'total_hours': float(aggregates['total_hours'] or 0),
            'normal_hours': float(aggregates['normal_hours'] or 0),
            'overtime_hours': float(aggregates['overtime_hours'] or 0),
            'task_count': query.count()
        }


class TaskStatusValidator:
    """
    Validates task status transitions and prerequisites.
    Ensures business rules are followed when changing task or work status.
    """
    
    @staticmethod
    def can_close_task(task):
        """
        Check if task can be closed.
        All assigned technicians must have departed from site.
        
        Args:
            task: Task instance
        
        Returns:
            tuple: (can_close: bool, error_message: str or None)
        """
        active_logs = TimeLog.objects.filter(
            task=task,
            departed_at__isnull=True
        )
        
        if active_logs.exists():
            technician_names = ', '.join([log.technician.full_name for log in active_logs])
            return False, f"Cannot close task. Technicians still on site: {technician_names}"
        
        return True, None
    
    @staticmethod
    def validate_close_task(task):
        """
        Validate that task can be closed (raises ValidationError if not).
        
        Args:
            task: Task instance
        
        Raises:
            ValidationError: If task cannot be closed
        """
        can_close, error_message = TaskStatusValidator.can_close_task(task)
        if not can_close:
            raise ValidationError(error_message)
    
    @staticmethod
    def can_mark_in_progress(assignment):
        """
        Check if work status can be set to in-progress.
        Technician must have traveled to or arrived at site.
        
        Args:
            assignment: TaskAssignment instance
        
        Returns:
            tuple: (can_mark: bool, error_message: str or None)
        """
        if not assignment.assignee:
            # Team assignments don't have this restriction
            return True, None
        
        time_log = TimeLog.objects.filter(
            task=assignment.task,
            technician=assignment.assignee
        ).first()
        
        if not time_log:
            return False, "Must travel to or arrive at site before marking as in-progress"
        
        if not time_log.travel_started_at and not time_log.arrived_at:
            return False, "Must travel to or arrive at site before marking as in-progress"
        
        return True, None
    
    @staticmethod
    def validate_mark_in_progress(assignment):
        """
        Validate that work status can be set to in-progress (raises ValidationError if not).
        
        Args:
            assignment: TaskAssignment instance
        
        Raises:
            ValidationError: If work status cannot be set to in-progress
        """
        can_mark, error_message = TaskStatusValidator.can_mark_in_progress(assignment)
        if not can_mark:
            raise ValidationError(error_message)
    
    @staticmethod
    def can_mark_done(assignment):
        """
        Check if work status can be set to done.
        Technician must have departed from site.
        
        Args:
            assignment: TaskAssignment instance
        
        Returns:
            tuple: (can_mark: bool, error_message: str or None)
        """
        if not assignment.assignee:
            # Team assignments don't have this restriction
            return True, None
        
        time_log = TimeLog.objects.filter(
            task=assignment.task,
            technician=assignment.assignee
        ).first()
        
        if not time_log:
            return False, "Must complete site visit before marking as done"
        
        if not time_log.departed_at:
            return False, "Must depart from site before marking as done"
        
        return True, None
    
    @staticmethod
    def validate_mark_done(assignment):
        """
        Validate that work status can be set to done (raises ValidationError if not).
        
        Args:
            assignment: TaskAssignment instance
        
        Raises:
            ValidationError: If work status cannot be set to done
        """
        can_mark, error_message = TaskStatusValidator.can_mark_done(assignment)
        if not can_mark:
            raise ValidationError(error_message)
    
    @staticmethod
    def validate_status_transition(task, new_status):
        """
        Validate task status transition.
        
        Args:
            task: Task instance
            new_status: New status value
        
        Raises:
            ValidationError: If status transition is invalid
        """
        old_status = task.status
        
        # Validate closing task
        if new_status == 'closed' and old_status != 'closed':
            TaskStatusValidator.validate_close_task(task)
        
        # Reset work status when reopening
        if new_status == 'reopened' and old_status == 'closed':
            # This will be handled in the view/serializer
            pass
    
    @staticmethod
    def validate_work_status_transition(assignment, new_work_status):
        """
        Validate work status transition.
        
        Args:
            assignment: TaskAssignment instance
            new_work_status: New work status value
        
        Raises:
            ValidationError: If work status transition is invalid
        """
        # Validate marking as in-progress
        if new_work_status == 'in_progress':
            TaskStatusValidator.validate_mark_in_progress(assignment)
        
        # Validate marking as done
        if new_work_status == 'done':
            TaskStatusValidator.validate_mark_done(assignment)
