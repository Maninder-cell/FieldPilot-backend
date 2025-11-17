"""
Equipment Report Generators

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.equipment.models import Equipment
from apps.tasks.models import Task
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report


@register_report('equipment_summary')
class EquipmentSummaryReportGenerator(BaseReportGenerator):
    """
    Generate summary report for equipment including counts by type,
    operational status, condition, and warranty information.
    """
    
    report_type = 'equipment_summary'
    report_name = 'Equipment Summary Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'equipment_type',
        'operational_status',
        'condition',
        'building',
        'facility',
        'customer',
    ]
    
    def get_queryset(self):
        """Get filtered equipment queryset."""
        queryset = Equipment.objects.all()
        
        # Apply type filter
        equipment_type = self.get_filter_value('equipment_type')
        if equipment_type:
            if isinstance(equipment_type, list):
                queryset = queryset.filter(equipment_type__in=equipment_type)
            else:
                queryset = queryset.filter(equipment_type=equipment_type)
        
        # Apply operational status filter
        operational_status = self.get_filter_value('operational_status')
        if operational_status:
            if isinstance(operational_status, list):
                queryset = queryset.filter(operational_status__in=operational_status)
            else:
                queryset = queryset.filter(operational_status=operational_status)
        
        # Apply condition filter
        condition = self.get_filter_value('condition')
        if condition:
            if isinstance(condition, list):
                queryset = queryset.filter(condition__in=condition)
            else:
                queryset = queryset.filter(condition=condition)
        
        # Apply building filter
        building_id = self.get_filter_value('building')
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        
        # Apply facility filter
        facility_id = self.get_filter_value('facility')
        if facility_id:
            queryset = queryset.filter(building__facility_id=facility_id)
        
        # Apply customer filter
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate equipment summary metrics."""
        total_equipment = queryset.count()
        
        # Count by type
        type_counts = queryset.values('equipment_type').annotate(count=Count('id'))
        by_type = {item['equipment_type']: item['count'] for item in type_counts}
        
        # Count by operational status
        status_counts = queryset.values('operational_status').annotate(count=Count('id'))
        by_operational_status = {item['operational_status']: item['count'] for item in status_counts}
        
        # Count by condition
        condition_counts = queryset.values('condition').annotate(count=Count('id'))
        by_condition = {item['condition']: item['count'] for item in condition_counts}
        
        # Warranty expiration alerts
        warranty_alerts = self._get_warranty_alerts(queryset)
        
        return {
            'summary': {
                'total_equipment': total_equipment,
                'operational': queryset.filter(operational_status='operational').count(),
                'maintenance': queryset.filter(operational_status='maintenance').count(),
                'broken': queryset.filter(operational_status='broken').count(),
                'retired': queryset.filter(operational_status='retired').count(),
            },
            'by_type': by_type,
            'by_operational_status': by_operational_status,
            'by_condition': by_condition,
            'warranty_alerts': warranty_alerts,
        }
    
    def _get_warranty_alerts(self, queryset):
        """Get equipment with warranties expiring soon."""
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        ninety_days = today + timedelta(days=90)
        
        expiring_soon = queryset.filter(
            warranty_expiration__gte=today,
            warranty_expiration__lte=thirty_days
        ).count()
        
        expiring_90_days = queryset.filter(
            warranty_expiration__gt=thirty_days,
            warranty_expiration__lte=ninety_days
        ).count()
        
        expired = queryset.filter(
            warranty_expiration__lt=today
        ).count()
        
        return {
            'expiring_within_30_days': expiring_soon,
            'expiring_within_90_days': expiring_90_days,
            'expired': expired,
        }


@register_report('equipment_detail')
class EquipmentDetailReportGenerator(BaseReportGenerator):
    """
    Generate detailed report for equipment with full information.
    """
    
    report_type = 'equipment_detail'
    report_name = 'Equipment Detail Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'equipment_type',
        'operational_status',
        'building',
        'facility',
        'customer',
        'limit',
        'offset',
    ]
    
    def get_queryset(self):
        """Get filtered equipment queryset with related data."""
        queryset = Equipment.objects.select_related(
            'building',
            'building__facility',
            'customer'
        )
        
        # Apply filters (same as summary)
        equipment_type = self.get_filter_value('equipment_type')
        if equipment_type:
            if isinstance(equipment_type, list):
                queryset = queryset.filter(equipment_type__in=equipment_type)
            else:
                queryset = queryset.filter(equipment_type=equipment_type)
        
        operational_status = self.get_filter_value('operational_status')
        if operational_status:
            if isinstance(operational_status, list):
                queryset = queryset.filter(operational_status__in=operational_status)
            else:
                queryset = queryset.filter(operational_status=operational_status)
        
        building_id = self.get_filter_value('building')
        if building_id:
            queryset = queryset.filter(building_id=building_id)
        
        facility_id = self.get_filter_value('facility')
        if facility_id:
            queryset = queryset.filter(building__facility_id=facility_id)
        
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        # Apply pagination
        limit = self.get_filter_value('limit', 100)
        offset = self.get_filter_value('offset', 0)
        queryset = queryset[offset:offset + limit]
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Format detailed equipment information."""
        equipment_data = []
        
        for equipment in queryset:
            equipment_data.append({
                'equipment_number': equipment.equipment_number,
                'name': equipment.name,
                'type': equipment.equipment_type,
                'manufacturer': equipment.manufacturer,
                'model': equipment.model,
                'serial_number': equipment.serial_number,
                'operational_status': equipment.operational_status,
                'condition': equipment.condition,
                'building': {
                    'id': str(equipment.building.id),
                    'name': equipment.building.name,
                } if equipment.building else None,
                'facility': {
                    'id': str(equipment.building.facility.id),
                    'name': equipment.building.facility.name,
                } if equipment.building and equipment.building.facility else None,
                'customer': {
                    'id': str(equipment.customer.id),
                    'name': equipment.customer.company_name,
                } if equipment.customer else None,
                'purchase_date': equipment.purchase_date,
                'purchase_price': float(equipment.purchase_price) if equipment.purchase_price else None,
                'warranty_expiration': equipment.warranty_expiration,
                'is_under_warranty': equipment.is_under_warranty,
                'installation_date': equipment.installation_date,
                'specifications': equipment.specifications,
            })
        
        return {
            'equipment': equipment_data,
            'total_count': len(equipment_data),
        }


@register_report('equipment_maintenance_history')
class EquipmentMaintenanceHistoryReportGenerator(BaseReportGenerator):
    """
    Generate maintenance history report for equipment showing all associated tasks.
    """
    
    report_type = 'equipment_maintenance_history'
    report_name = 'Equipment Maintenance History Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'equipment',
        'equipment_type',
        'start_date',
        'end_date',
    ]
    
    def get_queryset(self):
        """Get equipment with maintenance history."""
        queryset = Equipment.objects.select_related(
            'building',
            'building__facility'
        ).prefetch_related(
            'tasks',
            'tasks__assignments',
            'tasks__time_logs'
        )
        
        # Apply equipment filter
        equipment_id = self.get_filter_value('equipment')
        if equipment_id:
            queryset = queryset.filter(id=equipment_id)
        
        # Apply type filter
        equipment_type = self.get_filter_value('equipment_type')
        if equipment_type:
            if isinstance(equipment_type, list):
                queryset = queryset.filter(equipment_type__in=equipment_type)
            else:
                queryset = queryset.filter(equipment_type=equipment_type)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate maintenance history metrics."""
        equipment_history = []
        
        for equipment in queryset:
            # Get tasks for this equipment
            tasks = equipment.tasks.all()
            
            # Apply date filter to tasks
            if 'start_date' in self.filters:
                tasks = tasks.filter(created_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                tasks = tasks.filter(created_at__lte=self.filters['end_date'])
            
            # Calculate maintenance metrics
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status='closed').count()
            
            # Get last maintenance date
            last_maintenance = tasks.filter(
                status='closed'
            ).order_by('-created_at').first()
            
            # Format task history
            task_history = []
            for task in tasks.order_by('-created_at')[:10]:  # Last 10 tasks
                task_history.append({
                    'task_number': task.task_number,
                    'title': task.title,
                    'status': task.status,
                    'priority': task.priority,
                    'created_at': task.created_at,
                    'scheduled_start': task.scheduled_start,
                    'scheduled_end': task.scheduled_end,
                })
            
            equipment_history.append({
                'equipment_number': equipment.equipment_number,
                'name': equipment.name,
                'type': equipment.equipment_type,
                'operational_status': equipment.operational_status,
                'maintenance_summary': {
                    'total_tasks': total_tasks,
                    'completed_tasks': completed_tasks,
                    'last_maintenance_date': last_maintenance.created_at if last_maintenance else None,
                },
                'recent_tasks': task_history,
            })
        
        return {
            'equipment_history': equipment_history,
            'total_equipment': len(equipment_history),
        }


@register_report('equipment_utilization')
class EquipmentUtilizationReportGenerator(BaseReportGenerator):
    """
    Generate equipment utilization report showing task counts and usage patterns.
    """
    
    report_type = 'equipment_utilization'
    report_name = 'Equipment Utilization Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'equipment_type',
        'start_date',
        'end_date',
        'facility',
    ]
    
    def get_queryset(self):
        """Get equipment with task counts."""
        queryset = Equipment.objects.select_related(
            'building',
            'building__facility'
        ).annotate(
            task_count=Count('tasks')
        )
        
        # Apply type filter
        equipment_type = self.get_filter_value('equipment_type')
        if equipment_type:
            if isinstance(equipment_type, list):
                queryset = queryset.filter(equipment_type__in=equipment_type)
            else:
                queryset = queryset.filter(equipment_type=equipment_type)
        
        # Apply facility filter
        facility_id = self.get_filter_value('facility')
        if facility_id:
            queryset = queryset.filter(building__facility_id=facility_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate utilization metrics."""
        utilization_data = []
        
        for equipment in queryset:
            # Get tasks in date range
            tasks = equipment.tasks.all()
            if 'start_date' in self.filters:
                tasks = tasks.filter(created_at__gte=self.filters['start_date'])
            if 'end_date' in self.filters:
                tasks = tasks.filter(created_at__lte=self.filters['end_date'])
            
            task_count = tasks.count()
            completed_count = tasks.filter(status='closed').count()
            
            utilization_data.append({
                'equipment_number': equipment.equipment_number,
                'name': equipment.name,
                'type': equipment.equipment_type,
                'operational_status': equipment.operational_status,
                'task_count': task_count,
                'completed_tasks': completed_count,
                'facility': {
                    'id': str(equipment.building.facility.id),
                    'name': equipment.building.facility.name,
                } if equipment.building and equipment.building.facility else None,
            })
        
        # Sort by task count
        utilization_data.sort(key=lambda x: x['task_count'], reverse=True)
        
        # Get most and least utilized
        most_utilized = utilization_data[:5] if len(utilization_data) >= 5 else utilization_data
        least_utilized = utilization_data[-5:] if len(utilization_data) >= 5 else []
        
        return {
            'utilization': utilization_data,
            'most_utilized': most_utilized,
            'least_utilized': least_utilized,
            'total_equipment': len(utilization_data),
        }
