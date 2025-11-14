"""
Service Request Report Generators

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Count, Avg, Q
from django.utils import timezone

from apps.service_requests.models import ServiceRequest
from apps.service_requests.reports import ServiceRequestReports
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report
from apps.reports.utils import calculate_percentage


@register_report('service_request_summary')
class ServiceRequestSummaryReportGenerator(BaseReportGenerator):
    """
    Generate summary report for service requests including counts by status,
    priority, type, conversion rate, response time, and customer satisfaction.
    Extends existing ServiceRequestReports functionality.
    """
    
    report_type = 'service_request_summary'
    report_name = 'Service Request Summary Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'start_date',
        'end_date',
        'status',
        'priority',
        'request_type',
        'customer',
    ]
    
    def get_queryset(self):
        """Get filtered service request queryset."""
        queryset = ServiceRequest.objects.all()
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at')
        
        # Apply status filter
        queryset = self.apply_status_filter(queryset)
        
        # Apply priority filter
        queryset = self.apply_priority_filter(queryset)
        
        # Apply request type filter
        request_type = self.get_filter_value('request_type')
        if request_type:
            if isinstance(request_type, list):
                queryset = queryset.filter(request_type__in=request_type)
            else:
                queryset = queryset.filter(request_type=request_type)
        
        # Apply customer filter
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate service request summary metrics."""
        total_requests = queryset.count()
        
        # Count by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        by_status = {item['status']: item['count'] for item in status_counts}
        
        # Count by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        by_priority = {item['priority']: item['count'] for item in priority_counts}
        
        # Count by request type
        type_counts = queryset.values('request_type').annotate(count=Count('id'))
        by_type = {item['request_type']: item['count'] for item in type_counts}
        
        # Calculate conversion rate
        accepted_count = queryset.filter(
            status__in=['accepted', 'in_progress', 'completed']
        ).count()
        converted_count = queryset.filter(converted_task__isnull=False).count()
        conversion_rate = calculate_percentage(converted_count, accepted_count)
        
        # Calculate average response time
        avg_response_time = self._calculate_avg_response_time(queryset)
        
        # Calculate average resolution time
        avg_resolution_time = self._calculate_avg_resolution_time(queryset)
        
        # Customer satisfaction metrics
        feedback_requests = queryset.filter(customer_rating__isnull=False)
        avg_rating = feedback_requests.aggregate(avg=Avg('customer_rating'))['avg']
        
        # Rating distribution
        rating_dist = feedback_requests.values('customer_rating').annotate(count=Count('id'))
        rating_distribution = {item['customer_rating']: item['count'] for item in rating_dist}
        
        return {
            'summary': {
                'total_requests': total_requests,
                'accepted_requests': accepted_count,
                'converted_to_tasks': converted_count,
                'conversion_rate_percent': conversion_rate,
                'avg_response_time_hours': avg_response_time,
                'avg_resolution_time_hours': avg_resolution_time,
            },
            'by_status': by_status,
            'by_priority': by_priority,
            'by_type': by_type,
            'customer_satisfaction': {
                'avg_rating': round(float(avg_rating), 2) if avg_rating else None,
                'total_feedback': feedback_requests.count(),
                'rating_distribution': rating_distribution,
            },
        }
    
    def _calculate_avg_response_time(self, queryset):
        """Calculate average time from creation to review."""
        reviewed_requests = queryset.filter(reviewed_at__isnull=False)
        
        if not reviewed_requests.exists():
            return None
        
        response_times = []
        for req in reviewed_requests:
            if req.reviewed_at and req.created_at:
                delta = req.reviewed_at - req.created_at
                response_times.append(delta.total_seconds() / 3600)
        
        if response_times:
            return round(sum(response_times) / len(response_times), 2)
        return None
    
    def _calculate_avg_resolution_time(self, queryset):
        """Calculate average time from creation to completion."""
        completed_requests = queryset.filter(
            status='completed',
            completed_at__isnull=False
        )
        
        if not completed_requests.exists():
            return None
        
        resolution_times = []
        for req in completed_requests:
            if req.completed_at and req.created_at:
                delta = req.completed_at - req.created_at
                resolution_times.append(delta.total_seconds() / 3600)
        
        if resolution_times:
            return round(sum(resolution_times) / len(resolution_times), 2)
        return None


@register_report('service_request_detail')
class ServiceRequestDetailReportGenerator(BaseReportGenerator):
    """
    Generate detailed report for service requests with full information
    including customer details, timeline, and converted task information.
    """
    
    report_type = 'service_request_detail'
    report_name = 'Service Request Detail Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'start_date',
        'end_date',
        'status',
        'priority',
        'request_type',
        'customer',
        'equipment',
        'limit',
        'offset',
    ]
    
    def get_queryset(self):
        """Get filtered service request queryset with related data."""
        queryset = ServiceRequest.objects.select_related(
            'customer',
            'equipment',
            'equipment__building',
            'equipment__building__facility',
            'reviewed_by',
            'converted_task'
        ).prefetch_related(
            'actions',
            'comments'
        )
        
        # Apply date filter
        queryset = self.apply_date_filter(queryset, 'created_at')
        
        # Apply status filter
        queryset = self.apply_status_filter(queryset)
        
        # Apply priority filter
        queryset = self.apply_priority_filter(queryset)
        
        # Apply request type filter
        request_type = self.get_filter_value('request_type')
        if request_type:
            if isinstance(request_type, list):
                queryset = queryset.filter(request_type__in=request_type)
            else:
                queryset = queryset.filter(request_type=request_type)
        
        # Apply customer filter
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        # Apply equipment filter
        equipment_id = self.get_filter_value('equipment')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        
        # Apply pagination
        limit = self.get_filter_value('limit', 100)
        offset = self.get_filter_value('offset', 0)
        queryset = queryset[offset:offset + limit]
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Format detailed service request information."""
        requests_data = []
        
        for request in queryset:
            # Calculate response time
            response_time = None
            if request.reviewed_at and request.created_at:
                delta = request.reviewed_at - request.created_at
                response_time = round(delta.total_seconds() / 3600, 2)
            
            # Calculate resolution time
            resolution_time = None
            if request.completed_at and request.created_at:
                delta = request.completed_at - request.created_at
                resolution_time = round(delta.total_seconds() / 3600, 2)
            
            # Get action timeline
            actions = []
            for action in request.actions.all().order_by('created_at'):
                actions.append({
                    'action_type': action.action_type,
                    'description': action.description,
                    'performed_by': action.performed_by.full_name if action.performed_by else None,
                    'created_at': action.created_at,
                })
            
            requests_data.append({
                'request_number': request.id,
                'title': request.title,
                'description': request.description,
                'status': request.status,
                'priority': request.priority,
                'request_type': request.request_type,
                'customer': {
                    'id': str(request.customer.id),
                    'name': request.customer.full_name,
                    'email': request.customer.email,
                    'company': request.customer.company_name,
                } if request.customer else None,
                'equipment': {
                    'id': str(request.equipment.id),
                    'number': request.equipment.equipment_number,
                    'name': request.equipment.name,
                } if request.equipment else None,
                'facility': {
                    'id': str(request.equipment.building.facility.id),
                    'name': request.equipment.building.facility.name,
                } if request.equipment and request.equipment.building and request.equipment.building.facility else None,
                'created_at': request.created_at,
                'reviewed_at': request.reviewed_at,
                'reviewed_by': request.reviewed_by.full_name if request.reviewed_by else None,
                'completed_at': request.completed_at,
                'response_time_hours': response_time,
                'resolution_time_hours': resolution_time,
                'customer_rating': request.customer_rating,
                'customer_feedback': request.customer_feedback,
                'converted_task': {
                    'task_number': request.converted_task.task_number,
                    'title': request.converted_task.title,
                    'status': request.converted_task.status,
                } if request.converted_task else None,
                'actions': actions,
            })
        
        return {
            'requests': requests_data,
            'total_count': len(requests_data),
        }
