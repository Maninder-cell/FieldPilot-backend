"""
Financial Report Generators

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db.models import Sum, Count, Q
from decimal import Decimal

from apps.tasks.models import Task, TimeLog, MaterialLog
from apps.facilities.models import Customer
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report


@register_report('labor_cost')
class LaborCostReportGenerator(BaseReportGenerator):
    """
    Generate labor cost report showing work hours and calculated costs
    based on hourly rates.
    """
    
    report_type = 'labor_cost'
    report_name = 'Labor Cost Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'start_date',
        'end_date',
        'technician',
        'task',
        'customer',
        'normal_hourly_rate',  # Default rate for normal hours
        'overtime_hourly_rate',  # Default rate for overtime
    ]
    
    def validate_filters(self):
        """Validate filters - require date range."""
        super().validate_filters()
        
        if 'start_date' not in self.filters or 'end_date' not in self.filters:
            raise ValueError("start_date and end_date are required for labor cost report")
    
    def get_queryset(self):
        """Get time logs for cost calculation."""
        queryset = TimeLog.objects.filter(
            departed_at__isnull=False
        ).select_related(
            'technician',
            'task',
            'task__equipment',
            'task__equipment__customer'
        )
        
        # Apply date filter
        if 'start_date' in self.filters:
            queryset = queryset.filter(departed_at__gte=self.filters['start_date'])
        if 'end_date' in self.filters:
            queryset = queryset.filter(departed_at__lte=self.filters['end_date'])
        
        # Apply technician filter
        technician_id = self.get_filter_value('technician')
        if technician_id:
            queryset = queryset.filter(technician_id=technician_id)
        
        # Apply task filter
        task_id = self.get_filter_value('task')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        # Apply customer filter
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(task__equipment__customer_id=customer_id)
        
        return queryset.order_by('technician', 'departed_at')
    
    def calculate_metrics(self, queryset):
        """Calculate labor costs."""
        # Get hourly rates from filters or use defaults
        normal_rate = Decimal(str(self.get_filter_value('normal_hourly_rate', 50)))
        overtime_rate = Decimal(str(self.get_filter_value('overtime_hourly_rate', 75)))
        
        # Group by technician
        technician_costs = {}
        task_costs = {}
        customer_costs = {}
        
        for log in queryset:
            tech_id = str(log.technician.id)
            task_id = str(log.task.id)
            
            # Calculate costs
            normal_cost = Decimal(str(log.normal_hours)) * normal_rate
            overtime_cost = Decimal(str(log.overtime_hours)) * overtime_rate
            total_cost = normal_cost + overtime_cost
            
            # Aggregate by technician
            if tech_id not in technician_costs:
                technician_costs[tech_id] = {
                    'technician': {
                        'id': tech_id,
                        'name': log.technician.full_name,
                    },
                    'normal_hours': 0,
                    'overtime_hours': 0,
                    'normal_cost': 0,
                    'overtime_cost': 0,
                    'total_cost': 0,
                }
            
            technician_costs[tech_id]['normal_hours'] += float(log.normal_hours)
            technician_costs[tech_id]['overtime_hours'] += float(log.overtime_hours)
            technician_costs[tech_id]['normal_cost'] += float(normal_cost)
            technician_costs[tech_id]['overtime_cost'] += float(overtime_cost)
            technician_costs[tech_id]['total_cost'] += float(total_cost)
            
            # Aggregate by task
            if task_id not in task_costs:
                task_costs[task_id] = {
                    'task': {
                        'id': task_id,
                        'task_number': log.task.task_number,
                        'title': log.task.title,
                    },
                    'total_hours': 0,
                    'total_cost': 0,
                }
            
            task_costs[task_id]['total_hours'] += float(log.total_work_hours)
            task_costs[task_id]['total_cost'] += float(total_cost)
            
            # Aggregate by customer
            if log.task.equipment and log.task.equipment.customer:
                customer_id = str(log.task.equipment.customer.id)
                if customer_id not in customer_costs:
                    customer_costs[customer_id] = {
                        'customer': {
                            'id': customer_id,
                            'name': log.task.equipment.customer.company_name,
                        },
                        'total_hours': 0,
                        'total_cost': 0,
                    }
                
                customer_costs[customer_id]['total_hours'] += float(log.total_work_hours)
                customer_costs[customer_id]['total_cost'] += float(total_cost)
        
        # Round all values
        for tech_id in technician_costs:
            for key in ['normal_hours', 'overtime_hours', 'normal_cost', 'overtime_cost', 'total_cost']:
                technician_costs[tech_id][key] = round(technician_costs[tech_id][key], 2)
        
        for task_id in task_costs:
            task_costs[task_id]['total_hours'] = round(task_costs[task_id]['total_hours'], 2)
            task_costs[task_id]['total_cost'] = round(task_costs[task_id]['total_cost'], 2)
        
        for customer_id in customer_costs:
            customer_costs[customer_id]['total_hours'] = round(customer_costs[customer_id]['total_hours'], 2)
            customer_costs[customer_id]['total_cost'] = round(customer_costs[customer_id]['total_cost'], 2)
        
        # Calculate grand totals
        grand_total_hours = sum(t['total_hours'] for t in task_costs.values())
        grand_total_cost = sum(t['total_cost'] for t in task_costs.values())
        
        return {
            'by_technician': list(technician_costs.values()),
            'by_task': list(task_costs.values()),
            'by_customer': list(customer_costs.values()),
            'summary': {
                'total_hours': round(grand_total_hours, 2),
                'total_cost': round(grand_total_cost, 2),
                'normal_hourly_rate': float(normal_rate),
                'overtime_hourly_rate': float(overtime_rate),
            },
        }


@register_report('materials_usage')
class MaterialsUsageReportGenerator(BaseReportGenerator):
    """
    Generate materials usage report showing materials needed vs received.
    """
    
    report_type = 'materials_usage'
    report_name = 'Materials Usage Report'
    cache_ttl = 1800  # 30 minutes
    
    available_filters = [
        'start_date',
        'end_date',
        'task',
        'material_name',
    ]
    
    def get_queryset(self):
        """Get material logs."""
        queryset = MaterialLog.objects.select_related(
            'task',
            'logged_by'
        )
        
        # Apply date filter
        if 'start_date' in self.filters:
            queryset = queryset.filter(logged_at__gte=self.filters['start_date'])
        if 'end_date' in self.filters:
            queryset = queryset.filter(logged_at__lte=self.filters['end_date'])
        
        # Apply task filter
        task_id = self.get_filter_value('task')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        # Apply material name filter
        material_name = self.get_filter_value('material_name')
        if material_name:
            queryset = queryset.filter(material_name__icontains=material_name)
        
        return queryset.order_by('task', 'logged_at')
    
    def calculate_metrics(self, queryset):
        """Calculate materials usage metrics."""
        # Group by task
        task_materials = {}
        material_summary = {}
        
        for log in queryset:
            task_id = str(log.task.id)
            
            # Aggregate by task
            if task_id not in task_materials:
                task_materials[task_id] = {
                    'task': {
                        'id': task_id,
                        'task_number': log.task.task_number,
                        'title': log.task.title,
                    },
                    'materials_needed': [],
                    'materials_received': [],
                }
            
            material_entry = {
                'material_name': log.material_name,
                'quantity': float(log.quantity),
                'unit': log.unit,
                'logged_at': log.logged_at,
                'logged_by': log.logged_by.full_name if log.logged_by else None,
            }
            
            if log.log_type == 'needed':
                task_materials[task_id]['materials_needed'].append(material_entry)
            else:
                task_materials[task_id]['materials_received'].append(material_entry)
            
            # Aggregate by material name
            if log.material_name not in material_summary:
                material_summary[log.material_name] = {
                    'material_name': log.material_name,
                    'unit': log.unit,
                    'total_needed': 0,
                    'total_received': 0,
                }
            
            if log.log_type == 'needed':
                material_summary[log.material_name]['total_needed'] += float(log.quantity)
            else:
                material_summary[log.material_name]['total_received'] += float(log.quantity)
        
        # Round quantities in material summary
        for material in material_summary.values():
            material['total_needed'] = round(material['total_needed'], 2)
            material['total_received'] = round(material['total_received'], 2)
            material['difference'] = round(material['total_received'] - material['total_needed'], 2)
        
        return {
            'by_task': list(task_materials.values()),
            'material_summary': list(material_summary.values()),
            'total_tasks': len(task_materials),
            'total_material_types': len(material_summary),
        }


@register_report('customer_billing')
class CustomerBillingReportGenerator(BaseReportGenerator):
    """
    Generate customer billing report aggregating labor and material costs.
    """
    
    report_type = 'customer_billing'
    report_name = 'Customer Billing Report'
    cache_ttl = 3600  # 1 hour
    
    available_filters = [
        'start_date',
        'end_date',
        'customer',
        'normal_hourly_rate',
        'overtime_hourly_rate',
    ]
    
    def validate_filters(self):
        """Validate filters - require date range."""
        super().validate_filters()
        
        if 'start_date' not in self.filters or 'end_date' not in self.filters:
            raise ValueError("start_date and end_date are required for billing report")
    
    def get_queryset(self):
        """Get customers with billable work."""
        queryset = Customer.objects.filter(status='active')
        
        # Apply customer filter
        customer_id = self.get_filter_value('customer')
        if customer_id:
            queryset = queryset.filter(id=customer_id)
        
        return queryset
    
    def calculate_metrics(self, queryset):
        """Calculate billing for each customer."""
        # Get hourly rates
        normal_rate = Decimal(str(self.get_filter_value('normal_hourly_rate', 50)))
        overtime_rate = Decimal(str(self.get_filter_value('overtime_hourly_rate', 75)))
        
        billing_data = []
        
        for customer in queryset:
            # Get time logs for this customer's equipment
            time_logs = TimeLog.objects.filter(
                task__equipment__customer=customer,
                departed_at__isnull=False,
                departed_at__gte=self.filters['start_date'],
                departed_at__lte=self.filters['end_date']
            )
            
            # Calculate labor costs
            total_normal_hours = time_logs.aggregate(
                total=Sum('normal_hours')
            )['total'] or 0
            
            total_overtime_hours = time_logs.aggregate(
                total=Sum('overtime_hours')
            )['total'] or 0
            
            labor_cost = (
                Decimal(str(total_normal_hours)) * normal_rate +
                Decimal(str(total_overtime_hours)) * overtime_rate
            )
            
            # Get tasks for this customer
            tasks = Task.objects.filter(
                equipment__customer=customer,
                created_at__gte=self.filters['start_date'],
                created_at__lte=self.filters['end_date']
            )
            
            # Get material logs for these tasks
            material_logs = MaterialLog.objects.filter(
                task__in=tasks,
                log_type='received'
            )
            
            # Count materials (we don't have prices, so just count)
            materials_count = material_logs.count()
            
            # Get task breakdown
            task_breakdown = []
            for task in tasks[:10]:  # Limit to 10 tasks for summary
                task_time_logs = time_logs.filter(task=task)
                task_hours = task_time_logs.aggregate(
                    total=Sum('total_work_hours')
                )['total'] or 0
                
                task_breakdown.append({
                    'task_number': task.task_number,
                    'title': task.title,
                    'status': task.status,
                    'work_hours': round(float(task_hours), 2),
                })
            
            billing_data.append({
                'customer': {
                    'id': str(customer.id),
                    'company_name': customer.company_name,
                    'contact_person': customer.contact_person,
                    'email': customer.email,
                },
                'labor': {
                    'normal_hours': round(float(total_normal_hours), 2),
                    'overtime_hours': round(float(total_overtime_hours), 2),
                    'total_hours': round(float(total_normal_hours) + float(total_overtime_hours), 2),
                    'labor_cost': round(float(labor_cost), 2),
                },
                'materials': {
                    'materials_received_count': materials_count,
                    'note': 'Material costs not available - prices not tracked',
                },
                'total_billable': round(float(labor_cost), 2),
                'total_tasks': tasks.count(),
                'task_breakdown': task_breakdown,
            })
        
        # Calculate grand totals
        grand_total_hours = sum(c['labor']['total_hours'] for c in billing_data)
        grand_total_cost = sum(c['total_billable'] for c in billing_data)
        
        return {
            'billing_by_customer': billing_data,
            'summary': {
                'total_customers': len(billing_data),
                'grand_total_hours': round(grand_total_hours, 2),
                'grand_total_billable': round(grand_total_cost, 2),
                'normal_hourly_rate': float(normal_rate),
                'overtime_hourly_rate': float(overtime_rate),
            },
        }
