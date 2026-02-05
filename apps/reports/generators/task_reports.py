"""
Task Report Generators

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Count, Avg, Q, Sum, F, ExpressionWrapper, DurationField
from django.utils import timezone
from datetime import timedelta

from apps.tasks.models import Task, TaskAssignment, TimeLog
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report
from apps.reports.utils import calculate_percentage


@register_report('task_summary')
class TaskSummaryReportGenerator(BaseReportGenerator):
    """
    Generate summary report for tasks including counts by status, priority,
    completion rates, and average completion time.
    """
    
    report_type = 'task_summary'
    report_name = 'Task Summary Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'start_date',
        'end_date',
        'status',
        'priority',
        'equipment',
    ]
    
    def get_queryset(self):
        """Get filtered task queryset."""
        queryset = Task.objects.all()
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at')
        
        # Apply status filter
        queryset = self.apply_status_filter(queryset)
        
        # Apply priority filter
        queryset = self.apply_priority_filter(queryset)
        
        # Apply equipment filter
        equipment_id = self.get_filter_value('equipment')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate summary metrics."""
        total_tasks = queryset.count()
        
        # Count by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        status_breakdown = {item['status']: item['count'] for item in status_counts}
        
        # Count by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        priority_breakdown = {item['priority']: item['count'] for item in priority_counts}
        
        # Calculate completion rate
        completed_count = queryset.filter(status='closed').count()
        completion_rate = calculate_percentage(completed_count, total_tasks)
        
        # Calculate average completion time for closed tasks
        avg_completion_time = self._calculate_avg_completion_time(queryset)
        
        # Count overdue tasks
        overdue_count = self._count_overdue_tasks(queryset)
        
        return {
            'summary': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_count,
                'completion_rate_percent': completion_rate,
                'overdue_tasks': overdue_count,
                'avg_completion_time_hours': avg_completion_time,
            },
            'by_status': status_breakdown,
            'by_priority': priority_breakdown,
        }
    
    def _calculate_avg_completion_time(self, queryset):
        """Calculate average time from creation to completion."""
        closed_tasks = queryset.filter(status='closed', created_at__isnull=False)
        
        if not closed_tasks.exists():
            return None
        
        completion_times = []
        for task in closed_tasks:
            # Find the most recent time log with departure
            last_log = task.time_logs.filter(departed_at__isnull=False).order_by('-departed_at').first()
            if last_log and last_log.departed_at:
                delta = last_log.departed_at - task.created_at
                completion_times.append(delta.total_seconds() / 3600)  # Convert to hours
        
        if completion_times:
            return round(sum(completion_times) / len(completion_times), 2)
        return None
    
    def _count_overdue_tasks(self, queryset):
        """Count tasks that are past their scheduled end date."""
        now = timezone.now()
        return queryset.filter(
            scheduled_end__lt=now,
            status__in=['new', 'reopened', 'pending']
        ).count()


@register_report('task_detail')
class TaskDetailReportGenerator(BaseReportGenerator):
    """
    Generate detailed report for tasks with full information including
    equipment, assignments, and work hours.
    """
    
    report_type = 'task_detail'
    report_name = 'Task Detail Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'start_date',
        'end_date',
        'status',
        'priority',
        'equipment',
        'assignee',
        'limit',
        'offset',
    ]
    
    def get_queryset(self):
        """Get filtered task queryset with related data."""
        queryset = Task.objects.select_related(
            'equipment',
            'equipment__building',
            'equipment__building__facility'
        ).prefetch_related(
            'assignments',
            'assignments__assignee',
            'assignments__team',
            'time_logs'
        )
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at')
        
        # Apply status filter
        queryset = self.apply_status_filter(queryset)
        
        # Apply priority filter
        queryset = self.apply_priority_filter(queryset)
        
        # Apply equipment filter
        equipment_id = self.get_filter_value('equipment')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        
        # Apply assignee filter
        assignee_id = self.get_filter_value('assignee')
        if assignee_id:
            queryset = queryset.filter(assignments__assignee_id=assignee_id).distinct()
        
        # Apply pagination
        limit = self.get_filter_value('limit', 100)
        offset = self.get_filter_value('offset', 0)
        queryset = queryset[offset:offset + limit]
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Format detailed task information."""
        tasks_data = []
        
        for task in queryset:
            # Get assigned technicians
            assignments = task.assignments.all()
            assigned_technicians = []
            for assignment in assignments:
                if assignment.assignee:
                    assigned_technicians.append({
                        'id': str(assignment.assignee.id),
                        'name': assignment.assignee.full_name,
                        'email': assignment.assignee.email,
                    })
                elif assignment.team:
                    assigned_technicians.append({
                        'id': str(assignment.team.id),
                        'name': f"Team: {assignment.team.name}",
                        'is_team': True,
                    })
            
            # Calculate total work hours
            total_work_hours = task.time_logs.aggregate(
                total=Sum('total_work_hours')
            )['total'] or 0
            
            # Calculate total overtime hours
            total_overtime = task.time_logs.aggregate(
                total=Sum('overtime_hours')
            )['total'] or 0
            
            tasks_data.append({
                'task_number': task.task_number,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'equipment': {
                    'id': str(task.equipment.id),
                    'number': task.equipment.equipment_number,
                    'name': task.equipment.name,
                    'type': task.equipment.equipment_type,
                } if task.equipment else None,
                'facility': {
                    'id': str(task.equipment.building.facility.id),
                    'name': task.equipment.building.facility.name,
                } if task.equipment and task.equipment.building and task.equipment.building.facility else None,
                'assigned_technicians': assigned_technicians,
                'scheduled_start': task.scheduled_start,
                'scheduled_end': task.scheduled_end,
                'created_at': task.created_at,
                'work_hours': {
                    'total_hours': float(total_work_hours),
                    'overtime_hours': float(total_overtime),
                },
            })
        
        return {
            'tasks': tasks_data,
            'total_count': len(tasks_data),
        }


@register_report('overdue_tasks')
class OverdueTasksReportGenerator(BaseReportGenerator):
    """
    Generate report for overdue tasks (past scheduled end date and not completed).
    """
    
    report_type = 'overdue_tasks'
    report_name = 'Overdue Tasks Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'priority',
        'equipment',
        'assignee',
    ]
    
    def get_queryset(self):
        """Get overdue tasks queryset."""
        now = timezone.now()
        
        queryset = Task.objects.filter(
            scheduled_end__lt=now,
            status__in=['new', 'reopened', 'pending']
        ).select_related(
            'equipment',
            'equipment__building',
            'equipment__building__facility'
        ).prefetch_related(
            'assignments',
            'assignments__assignee'
        )
        
        # Apply priority filter
        queryset = self.apply_priority_filter(queryset)
        
        # Apply equipment filter
        equipment_id = self.get_filter_value('equipment')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        
        # Apply assignee filter
        assignee_id = self.get_filter_value('assignee')
        if assignee_id:
            queryset = queryset.filter(assignments__assignee_id=assignee_id).distinct()
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate overdue task metrics."""
        now = timezone.now()
        overdue_tasks = []
        
        # Group by priority
        by_priority = {}
        
        for task in queryset:
            days_overdue = (now - task.scheduled_end).days
            
            # Get assigned technicians
            assigned_technicians = []
            for assignment in task.assignments.all():
                if assignment.assignee:
                    assigned_technicians.append({
                        'id': str(assignment.assignee.id),
                        'name': assignment.assignee.full_name,
                    })
            
            task_data = {
                'task_number': task.task_number,
                'title': task.title,
                'priority': task.priority,
                'status': task.status,
                'scheduled_end': task.scheduled_end,
                'days_overdue': days_overdue,
                'equipment': {
                    'id': str(task.equipment.id),
                    'number': task.equipment.equipment_number,
                    'name': task.equipment.name,
                } if task.equipment else None,
                'assigned_technicians': assigned_technicians,
            }
            
            overdue_tasks.append(task_data)
            
            # Group by priority
            if task.priority not in by_priority:
                by_priority[task.priority] = []
            by_priority[task.priority].append(task_data)
        
        return {
            'summary': {
                'total_overdue': len(overdue_tasks),
                'by_priority_count': {
                    priority: len(tasks) for priority, tasks in by_priority.items()
                },
            },
            'overdue_tasks': overdue_tasks,
            'by_priority': by_priority,
        }
