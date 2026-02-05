"""
Technician Report Generators

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone

from apps.authentication.models import User
from apps.tasks.models import Task, TaskAssignment, TimeLog, TechnicianTeam
from apps.service_requests.models import ServiceRequest
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report


@register_report('technician_worksheet')
class TechnicianWorksheetGenerator(BaseReportGenerator):
    """
    Generate technician worksheet showing task assignments, time logs,
    work hours, and overtime for a specific date range.
    """
    
    report_type = 'technician_worksheet'
    report_name = 'Technician Worksheet Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'technician',
        'start_date',
        'end_date',
    ]
    
    def validate_filters(self):
        """Validate filters - require date range."""
        super().validate_filters()
        
        if 'start_date' not in self.filters or 'end_date' not in self.filters:
            raise ValueError("start_date and end_date are required for technician worksheet")
    
    def get_queryset(self):
        """Get time logs for technicians in date range."""
        queryset = TimeLog.objects.select_related(
            'technician',
            'task',
            'task__equipment'
        ).filter(
            departed_at__isnull=False  # Only completed time logs
        )
        
        # Apply date filter on departed_at
        if 'start_date' in self.filters:
            queryset = queryset.filter(departed_at__gte=self.filters['start_date'])
        if 'end_date' in self.filters:
            queryset = queryset.filter(departed_at__lte=self.filters['end_date'])
        
        # Apply technician filter
        technician_id = self.get_filter_value('technician')
        if technician_id:
            queryset = queryset.filter(technician_id=technician_id)
        
        return queryset.order_by('technician', 'departed_at')
    
    def calculate_metrics(self, queryset):
        """Calculate worksheet metrics by technician."""
        # Group by technician
        technician_worksheets = {}
        
        for log in queryset:
            tech_id = str(log.technician.id)
            
            if tech_id not in technician_worksheets:
                technician_worksheets[tech_id] = {
                    'technician': {
                        'id': tech_id,
                        'name': log.technician.full_name,
                        'email': log.technician.email,
                    },
                    'time_logs': [],
                    'totals': {
                        'total_work_hours': 0,
                        'normal_hours': 0,
                        'overtime_hours': 0,
                        'total_tasks': 0,
                    }
                }
            
            # Add time log entry
            technician_worksheets[tech_id]['time_logs'].append({
                'task_number': log.task.task_number,
                'task_title': log.task.title,
                'equipment': {
                    'number': log.task.equipment.equipment_number,
                    'name': log.task.equipment.name,
                } if log.task.equipment else None,
                'travel_started_at': log.travel_started_at,
                'arrived_at': log.arrived_at,
                'departed_at': log.departed_at,
                'lunch_started_at': log.lunch_started_at,
                'lunch_ended_at': log.lunch_ended_at,
                'equipment_status_at_departure': log.equipment_status_at_departure,
                'total_work_hours': float(log.total_work_hours),
                'normal_hours': float(log.normal_hours),
                'overtime_hours': float(log.overtime_hours),
            })
            
            # Update totals
            technician_worksheets[tech_id]['totals']['total_work_hours'] += float(log.total_work_hours)
            technician_worksheets[tech_id]['totals']['normal_hours'] += float(log.normal_hours)
            technician_worksheets[tech_id]['totals']['overtime_hours'] += float(log.overtime_hours)
        
        # Count unique tasks per technician
        for tech_id in technician_worksheets:
            unique_tasks = set(log['task_number'] for log in technician_worksheets[tech_id]['time_logs'])
            technician_worksheets[tech_id]['totals']['total_tasks'] = len(unique_tasks)
            
            # Round totals
            technician_worksheets[tech_id]['totals']['total_work_hours'] = round(
                technician_worksheets[tech_id]['totals']['total_work_hours'], 2
            )
            technician_worksheets[tech_id]['totals']['normal_hours'] = round(
                technician_worksheets[tech_id]['totals']['normal_hours'], 2
            )
            technician_worksheets[tech_id]['totals']['overtime_hours'] = round(
                technician_worksheets[tech_id]['totals']['overtime_hours'], 2
            )
        
        return {
            'worksheets': list(technician_worksheets.values()),
            'total_technicians': len(technician_worksheets),
        }


@register_report('technician_performance')
class TechnicianPerformanceReportGenerator(BaseReportGenerator):
    """
    Generate technician performance report showing completed tasks,
    work hours, and customer ratings.
    """
    
    report_type = 'technician_performance'
    report_name = 'Technician Performance Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'technician',
        'start_date',
        'end_date',
    ]
    
    def get_queryset(self):
        """Get technicians with performance data."""
        # Get active users who have task assignments (technicians)
        queryset = User.objects.filter(
            is_active=True,
            task_assignments__isnull=False
        ).distinct()
        
        # Apply technician filter
        technician_id = self.get_filter_value('technician')
        if technician_id:
            queryset = queryset.filter(id=technician_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate performance metrics for each technician."""
        performance_data = []
        
        for technician in queryset:
            # Get completed tasks
            completed_tasks = Task.objects.filter(
                assignments__assignee=technician,
                status='closed'
            ).distinct()
            
            # Apply date filter
            if 'start_date' in self.filters:
                completed_tasks = completed_tasks.filter(created_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                completed_tasks = completed_tasks.filter(created_at__lte=self.filters['end_date'])
            
            # Get time logs
            time_logs = TimeLog.objects.filter(
                technician=technician,
                departed_at__isnull=False
            )
            
            # Apply date filter to time logs
            if 'start_date' in self.filters:
                time_logs = time_logs.filter(departed_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                time_logs = time_logs.filter(departed_at__lte=self.filters['end_date'])
            
            # Calculate total work hours
            total_hours = time_logs.aggregate(
                total=Sum('total_work_hours')
            )['total'] or 0
            
            # Calculate average task completion time
            avg_completion_time = self._calculate_avg_completion_time(completed_tasks)
            
            # Get customer ratings from service requests
            service_requests = ServiceRequest.objects.filter(
                converted_task__in=completed_tasks,
                customer_rating__isnull=False
            )
            
            avg_rating = service_requests.aggregate(
                avg=Avg('customer_rating')
            )['avg']
            
            performance_data.append({
                'technician': {
                    'id': str(technician.id),
                    'name': technician.full_name,
                    'email': technician.email,
                },
                'completed_tasks': completed_tasks.count(),
                'total_work_hours': round(float(total_hours), 2),
                'avg_task_completion_time_hours': avg_completion_time,
                'customer_rating': {
                    'average': round(float(avg_rating), 2) if avg_rating else None,
                    'total_ratings': service_requests.count(),
                },
            })
        
        return {
            'performance': performance_data,
            'total_technicians': len(performance_data),
        }
    
    def _calculate_avg_completion_time(self, tasks):
        """Calculate average time from task creation to completion."""
        if not tasks.exists():
            return None
        
        completion_times = []
        for task in tasks:
            last_log = task.time_logs.filter(departed_at__isnull=False).order_by('-departed_at').first()
            if last_log and last_log.departed_at:
                delta = last_log.departed_at - task.created_at
                completion_times.append(delta.total_seconds() / 3600)
        
        if completion_times:
            return round(sum(completion_times) / len(completion_times), 2)
        return None


@register_report('technician_productivity')
class TechnicianProductivityReportGenerator(BaseReportGenerator):
    """
    Generate technician productivity report showing tasks per day
    and hours per task.
    """
    
    report_type = 'technician_productivity'
    report_name = 'Technician Productivity Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'technician',
        'start_date',
        'end_date',
    ]
    
    def validate_filters(self):
        """Validate filters - require date range."""
        super().validate_filters()
        
        if 'start_date' not in self.filters or 'end_date' not in self.filters:
            raise ValueError("start_date and end_date are required for productivity report")
    
    def get_queryset(self):
        """Get technicians."""
        # Get active users who have task assignments (technicians)
        queryset = User.objects.filter(
            is_active=True,
            task_assignments__isnull=False
        ).distinct()
        
        technician_id = self.get_filter_value('technician')
        if technician_id:
            queryset = queryset.filter(id=technician_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate productivity metrics."""
        productivity_data = []
        
        # Calculate date range in days
        date_range_days = (self.filters['end_date'] - self.filters['start_date']).days + 1
        
        for technician in queryset:
            # Get completed tasks in date range
            completed_tasks = Task.objects.filter(
                assignments__assignee=technician,
                status='closed',
                created_at__gte=self.filters['start_date'],
                created_at__lte=self.filters['end_date']
            ).distinct()
            
            # Get time logs in date range
            time_logs = TimeLog.objects.filter(
                technician=technician,
                departed_at__isnull=False,
                departed_at__gte=self.filters['start_date'],
                departed_at__lte=self.filters['end_date']
            )
            
            total_hours = time_logs.aggregate(total=Sum('total_work_hours'))['total'] or 0
            total_tasks = completed_tasks.count()
            
            # Calculate metrics
            tasks_per_day = round(total_tasks / date_range_days, 2) if date_range_days > 0 else 0
            hours_per_task = round(float(total_hours) / total_tasks, 2) if total_tasks > 0 else 0
            
            productivity_data.append({
                'technician': {
                    'id': str(technician.id),
                    'name': technician.full_name,
                },
                'completed_tasks': total_tasks,
                'total_work_hours': round(float(total_hours), 2),
                'tasks_per_day': tasks_per_day,
                'hours_per_task': hours_per_task,
                'date_range_days': date_range_days,
            })
        
        return {
            'productivity': productivity_data,
            'total_technicians': len(productivity_data),
        }


@register_report('team_performance')
class TeamPerformanceReportGenerator(BaseReportGenerator):
    """
    Generate team performance report with aggregated metrics.
    """
    
    report_type = 'team_performance'
    report_name = 'Team Performance Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'team',
        'start_date',
        'end_date',
    ]
    
    def get_queryset(self):
        """Get teams."""
        queryset = TechnicianTeam.objects.filter(is_active=True).prefetch_related('members')
        
        team_id = self.get_filter_value('team')
        if team_id:
            queryset = queryset.filter(id=team_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate team performance metrics."""
        team_data = []
        
        for team in queryset:
            members = team.members.filter(is_active=True)
            
            # Aggregate tasks for all team members
            team_tasks = Task.objects.filter(
                Q(assignments__assignee__in=members) | Q(assignments__team=team)
            ).distinct()
            
            # Apply date filter
            if 'start_date' in self.filters:
                team_tasks = team_tasks.filter(created_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                team_tasks = team_tasks.filter(created_at__lte=self.filters['end_date'])
            
            completed_tasks = team_tasks.filter(status='closed').count()
            total_tasks = team_tasks.count()
            
            # Aggregate work hours for all team members
            time_logs = TimeLog.objects.filter(
                technician__in=members,
                departed_at__isnull=False
            )
            
            if 'start_date' in self.filters:
                time_logs = time_logs.filter(departed_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                time_logs = time_logs.filter(departed_at__lte=self.filters['end_date'])
            
            total_hours = time_logs.aggregate(total=Sum('total_work_hours'))['total'] or 0
            
            # Individual member contributions
            member_contributions = []
            for member in members:
                member_tasks = team_tasks.filter(assignments__assignee=member).distinct().count()
                member_hours = time_logs.filter(technician=member).aggregate(
                    total=Sum('total_work_hours')
                )['total'] or 0
                
                member_contributions.append({
                    'technician': {
                        'id': str(member.id),
                        'name': member.full_name,
                    },
                    'tasks_completed': member_tasks,
                    'work_hours': round(float(member_hours), 2),
                })
            
            team_data.append({
                'team': {
                    'id': str(team.id),
                    'name': team.name,
                },
                'total_members': members.count(),
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
                'total_work_hours': round(float(total_hours), 2),
                'member_contributions': member_contributions,
            })
        
        return {
            'teams': team_data,
            'total_teams': len(team_data),
        }


@register_report('overtime_report')
class OvertimeReportGenerator(BaseReportGenerator):
    """
    Generate overtime report showing technicians with overtime hours.
    """
    
    report_type = 'overtime_report'
    report_name = 'Overtime Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'technician',
        'start_date',
        'end_date',
        'hourly_rate',  # Optional: for cost calculation
    ]
    
    def validate_filters(self):
        """Validate filters - require date range."""
        super().validate_filters()
        
        if 'start_date' not in self.filters or 'end_date' not in self.filters:
            raise ValueError("start_date and end_date are required for overtime report")
    
    def get_queryset(self):
        """Get time logs with overtime."""
        queryset = TimeLog.objects.filter(
            overtime_hours__gt=0,
            departed_at__isnull=False
        ).select_related('technician', 'task')
        
        # Apply date filter
        if 'start_date' in self.filters:
            queryset = queryset.filter(departed_at__gte=self.filters['start_date'])
        if 'end_date' in self.filters:
            queryset = queryset.filter(departed_at__lte=self.filters['end_date'])
        
        # Apply technician filter
        technician_id = self.get_filter_value('technician')
        if technician_id:
            queryset = queryset.filter(technician_id=technician_id)
        
        return queryset.order_by('technician', 'departed_at')
    
    def calculate_metrics(self, queryset):
        """Calculate overtime metrics."""
        # Get tenant default overtime rate
        tenant_overtime_rate = 0
        try:
            from apps.tenants.models import TenantSettings
            tenant_settings = TenantSettings.objects.first()
            if tenant_settings:
                tenant_overtime_rate = float(tenant_settings.default_overtime_hourly_rate)
        except Exception:
            pass
        
        # Group by technician
        technician_overtime = {}
        hourly_rate = self.get_filter_value('hourly_rate', tenant_overtime_rate)
        overtime_multiplier = 1.5  # Standard overtime multiplier (not used when rate is provided directly)
        
        for log in queryset:
            tech_id = str(log.technician.id)
            
            if tech_id not in technician_overtime:
                technician_overtime[tech_id] = {
                    'technician': {
                        'id': tech_id,
                        'name': log.technician.full_name,
                        'email': log.technician.email,
                    },
                    'overtime_logs': [],
                    'total_overtime_hours': 0,
                    'total_overtime_cost': 0,
                }
            
            overtime_hours = float(log.overtime_hours)
            overtime_cost = overtime_hours * hourly_rate * overtime_multiplier if hourly_rate > 0 else 0
            
            technician_overtime[tech_id]['overtime_logs'].append({
                'date': log.departed_at.date(),
                'task_number': log.task.task_number,
                'overtime_hours': overtime_hours,
                'overtime_cost': round(overtime_cost, 2) if hourly_rate > 0 else None,
            })
            
            technician_overtime[tech_id]['total_overtime_hours'] += overtime_hours
            technician_overtime[tech_id]['total_overtime_cost'] += overtime_cost
        
        # Round totals
        for tech_id in technician_overtime:
            technician_overtime[tech_id]['total_overtime_hours'] = round(
                technician_overtime[tech_id]['total_overtime_hours'], 2
            )
            technician_overtime[tech_id]['total_overtime_cost'] = round(
                technician_overtime[tech_id]['total_overtime_cost'], 2
            ) if hourly_rate > 0 else None
        
        # Calculate grand totals
        grand_total_hours = sum(t['total_overtime_hours'] for t in technician_overtime.values())
        grand_total_cost = sum(
            t['total_overtime_cost'] for t in technician_overtime.values() if t['total_overtime_cost']
        ) if hourly_rate > 0 else None
        
        return {
            'overtime_by_technician': list(technician_overtime.values()),
            'summary': {
                'total_technicians_with_overtime': len(technician_overtime),
                'grand_total_overtime_hours': round(grand_total_hours, 2),
                'grand_total_overtime_cost': round(grand_total_cost, 2) if grand_total_cost else None,
                'hourly_rate_used': hourly_rate if hourly_rate > 0 else None,
            },
        }
