"""
Service Request Reports and Analytics

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import timedelta
from .models import ServiceRequest, RequestAction


class ServiceRequestReports:
    """
    Generate reports and analytics for service requests.
    Task 17: Reporting and analytics
    """
    
    @staticmethod
    def get_overview_metrics(start_date=None, end_date=None):
        """
        Get overview metrics for service requests.
        Task 17.1: Admin reports endpoint
        """
        queryset = ServiceRequest.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Total counts by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        # Total counts by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        
        # Total counts by request type
        type_counts = queryset.values('request_type').annotate(count=Count('id'))
        
        # Average response time (time from created to reviewed)
        reviewed_requests = queryset.filter(reviewed_at__isnull=False)
        avg_response_time = None
        if reviewed_requests.exists():
            response_times = []
            for req in reviewed_requests:
                if req.reviewed_at and req.created_at:
                    delta = req.reviewed_at - req.created_at
                    response_times.append(delta.total_seconds() / 3600)  # hours
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        # Average resolution time (time from created to completed)
        completed_requests = queryset.filter(status='completed', completed_at__isnull=False)
        avg_resolution_time = None
        if completed_requests.exists():
            resolution_times = []
            for req in completed_requests:
                if req.completed_at and req.created_at:
                    delta = req.completed_at - req.created_at
                    resolution_times.append(delta.total_seconds() / 3600)  # hours
            if resolution_times:
                avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        # Conversion rate (accepted requests converted to tasks)
        accepted_count = queryset.filter(status__in=['accepted', 'in_progress', 'completed']).count()
        converted_count = queryset.filter(converted_task__isnull=False).count()
        conversion_rate = (converted_count / accepted_count * 100) if accepted_count > 0 else 0
        
        # Customer satisfaction
        feedback_requests = queryset.filter(customer_rating__isnull=False)
        avg_rating = feedback_requests.aggregate(avg=Avg('customer_rating'))['avg']
        
        return {
            'total_requests': queryset.count(),
            'status_breakdown': {item['status']: item['count'] for item in status_counts},
            'priority_breakdown': {item['priority']: item['count'] for item in priority_counts},
            'type_breakdown': {item['request_type']: item['count'] for item in type_counts},
            'avg_response_time_hours': round(avg_response_time, 2) if avg_response_time else None,
            'avg_resolution_time_hours': round(avg_resolution_time, 2) if avg_resolution_time else None,
            'conversion_rate_percent': round(conversion_rate, 2),
            'avg_customer_rating': round(avg_rating, 2) if avg_rating else None,
            'total_feedback': feedback_requests.count(),
        }
    
    @staticmethod
    def get_customer_metrics(customer_id, start_date=None, end_date=None):
        """
        Get metrics for a specific customer.
        """
        queryset = ServiceRequest.objects.filter(customer_id=customer_id)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return {
            'total_requests': queryset.count(),
            'pending': queryset.filter(status='pending').count(),
            'in_progress': queryset.filter(status='in_progress').count(),
            'completed': queryset.filter(status='completed').count(),
            'rejected': queryset.filter(status='rejected').count(),
            'avg_rating': queryset.filter(customer_rating__isnull=False).aggregate(
                avg=Avg('customer_rating')
            )['avg'],
        }
    
    @staticmethod
    def get_equipment_metrics(equipment_id, start_date=None, end_date=None):
        """
        Get metrics for a specific equipment.
        """
        queryset = ServiceRequest.objects.filter(equipment_id=equipment_id)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return {
            'total_requests': queryset.count(),
            'by_type': queryset.values('request_type').annotate(count=Count('id')),
            'by_priority': queryset.values('priority').annotate(count=Count('id')),
            'completed': queryset.filter(status='completed').count(),
        }
    
    @staticmethod
    def get_time_series_data(start_date, end_date, granularity='day'):
        """
        Get time series data for requests.
        """
        queryset = ServiceRequest.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        if granularity == 'day':
            data = queryset.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
        else:  # month
            data = queryset.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                count=Count('id')
            ).order_by('month')
        
        return list(data)
    
    @staticmethod
    def get_pending_requests_count():
        """
        Get count of pending requests.
        Task 17.2: Dashboard analytics
        """
        return ServiceRequest.objects.filter(status='pending').count()
    
    @staticmethod
    def get_overdue_requests():
        """
        Get overdue requests (pending for more than 24 hours).
        """
        threshold = timezone.now() - timedelta(hours=24)
        return ServiceRequest.objects.filter(
            status='pending',
            created_at__lt=threshold
        ).count()
    
    @staticmethod
    def get_customer_satisfaction_metrics():
        """
        Get customer satisfaction metrics.
        """
        feedback_requests = ServiceRequest.objects.filter(
            customer_rating__isnull=False
        )
        
        if not feedback_requests.exists():
            return {
                'avg_rating': None,
                'total_feedback': 0,
                'rating_distribution': {},
            }
        
        avg_rating = feedback_requests.aggregate(avg=Avg('customer_rating'))['avg']
        rating_dist = feedback_requests.values('customer_rating').annotate(
            count=Count('id')
        )
        
        return {
            'avg_rating': round(avg_rating, 2) if avg_rating else None,
            'total_feedback': feedback_requests.count(),
            'rating_distribution': {
                item['customer_rating']: item['count'] 
                for item in rating_dist
            },
        }
    
    @staticmethod
    def get_technician_performance_metrics():
        """
        Get technician performance metrics based on completed tasks.
        """
        from apps.tasks.models import Task
        from apps.authentication.models import User
        
        # Get technicians
        technicians = User.objects.filter(role='technician', is_active=True)
        
        performance_data = []
        for tech in technicians:
            # Get tasks assigned to this technician
            completed_tasks = Task.objects.filter(
                assignments__assignee=tech,
                status='completed'
            ).distinct()
            
            # Get service requests that led to these tasks
            requests_with_feedback = ServiceRequest.objects.filter(
                converted_task__in=completed_tasks,
                customer_rating__isnull=False
            )
            
            avg_rating = requests_with_feedback.aggregate(
                avg=Avg('customer_rating')
            )['avg']
            
            performance_data.append({
                'technician_id': str(tech.id),
                'technician_name': tech.full_name,
                'completed_tasks': completed_tasks.count(),
                'avg_customer_rating': round(avg_rating, 2) if avg_rating else None,
                'feedback_count': requests_with_feedback.count(),
            })
        
        return performance_data
