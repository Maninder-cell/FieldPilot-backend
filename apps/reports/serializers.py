"""
Reports Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import ReportAuditLog, ReportSchedule


class ReportMetadataSerializer(serializers.Serializer):
    """
    Serializer for report metadata.
    """
    report_type = serializers.CharField()
    report_name = serializers.CharField()
    generated_at = serializers.DateTimeField()
    generated_by = serializers.DictField()
    filters = serializers.DictField()


class ReportDataSerializer(serializers.Serializer):
    """
    Generic serializer for report data.
    """
    report_type = serializers.CharField()
    report_name = serializers.CharField()
    generated_at = serializers.DateTimeField()
    generated_by = serializers.DictField()
    filters = serializers.DictField()
    data = serializers.DictField()


class ReportAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for report audit logs.
    """
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportAuditLog
        fields = [
            'id',
            'user',
            'user_name',
            'report_type',
            'report_name',
            'filters',
            'format',
            'generated_at',
            'execution_time',
            'status',
            'error_message',
            'file_path',
            'file_size',
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        """Get user's full name."""
        return obj.user.full_name if obj.user else None


class ReportScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for report schedules.
    """
    created_by_name = serializers.SerializerMethodField()
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    
    class Meta:
        model = ReportSchedule
        fields = [
            'id',
            'name',
            'report_type',
            'filters',
            'format',
            'format_display',
            'frequency',
            'frequency_display',
            'day_of_week',
            'day_of_month',
            'time_of_day',
            'recipients',
            'is_active',
            'last_run',
            'next_run',
            'created_at',
            'created_by',
            'created_by_name',
            'updated_at',
        ]
        read_only_fields = ['id', 'last_run', 'next_run', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        """Get creator's full name."""
        return obj.created_by.full_name if obj.created_by else None
    
    def validate(self, data):
        """Validate schedule data."""
        frequency = data.get('frequency')
        
        # Validate weekly schedule
        if frequency == 'weekly':
            if 'day_of_week' not in data or data['day_of_week'] is None:
                raise serializers.ValidationError({
                    'day_of_week': 'Day of week is required for weekly schedules.'
                })
            if not (0 <= data['day_of_week'] <= 6):
                raise serializers.ValidationError({
                    'day_of_week': 'Day of week must be between 0 (Monday) and 6 (Sunday).'
                })
        
        # Validate monthly schedule
        if frequency == 'monthly':
            if 'day_of_month' not in data or data['day_of_month'] is None:
                raise serializers.ValidationError({
                    'day_of_month': 'Day of month is required for monthly schedules.'
                })
            if not (1 <= data['day_of_month'] <= 31):
                raise serializers.ValidationError({
                    'day_of_month': 'Day of month must be between 1 and 31.'
                })
        
        # Validate recipients
        if 'recipients' in data:
            if not data['recipients'] or len(data['recipients']) == 0:
                raise serializers.ValidationError({
                    'recipients': 'At least one recipient email is required.'
                })
        
        return data


class CreateReportScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for creating report schedules.
    """
    
    class Meta:
        model = ReportSchedule
        fields = [
            'name',
            'report_type',
            'filters',
            'format',
            'frequency',
            'day_of_week',
            'day_of_month',
            'time_of_day',
            'recipients',
            'is_active',
        ]
    
    def validate(self, data):
        """Validate schedule data."""
        frequency = data.get('frequency')
        
        # Validate weekly schedule
        if frequency == 'weekly':
            if 'day_of_week' not in data or data['day_of_week'] is None:
                raise serializers.ValidationError({
                    'day_of_week': 'Day of week is required for weekly schedules.'
                })
        
        # Validate monthly schedule
        if frequency == 'monthly':
            if 'day_of_month' not in data or data['day_of_month'] is None:
                raise serializers.ValidationError({
                    'day_of_month': 'Day of month is required for monthly schedules.'
                })
        
        # Validate recipients
        if not data.get('recipients') or len(data['recipients']) == 0:
            raise serializers.ValidationError({
                'recipients': 'At least one recipient email is required.'
            })
        
        return data


class UpdateReportScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for updating report schedules.
    """
    
    class Meta:
        model = ReportSchedule
        fields = [
            'name',
            'filters',
            'format',
            'frequency',
            'day_of_week',
            'day_of_month',
            'time_of_day',
            'recipients',
            'is_active',
        ]
    
    def validate(self, data):
        """Validate schedule data."""
        # Get current frequency if not in data
        frequency = data.get('frequency', self.instance.frequency if self.instance else None)
        
        # Validate weekly schedule
        if frequency == 'weekly':
            day_of_week = data.get('day_of_week', self.instance.day_of_week if self.instance else None)
            if day_of_week is None:
                raise serializers.ValidationError({
                    'day_of_week': 'Day of week is required for weekly schedules.'
                })
        
        # Validate monthly schedule
        if frequency == 'monthly':
            day_of_month = data.get('day_of_month', self.instance.day_of_month if self.instance else None)
            if day_of_month is None:
                raise serializers.ValidationError({
                    'day_of_month': 'Day of month is required for monthly schedules.'
                })
        
        # Validate recipients if provided
        if 'recipients' in data:
            if not data['recipients'] or len(data['recipients']) == 0:
                raise serializers.ValidationError({
                    'recipients': 'At least one recipient email is required.'
                })
        
        return data


class GenerateReportSerializer(serializers.Serializer):
    """
    Serializer for report generation request.
    """
    # Define all available report types
    REPORT_TYPE_CHOICES = [
        ('task_summary', 'Task Summary'),
        ('task_detail', 'Task Detail'),
        ('overdue_tasks', 'Overdue Tasks'),
        ('equipment_summary', 'Equipment Summary'),
        ('equipment_detail', 'Equipment Detail'),
        ('equipment_maintenance_history', 'Equipment Maintenance History'),
        ('equipment_utilization', 'Equipment Utilization'),
        ('technician_worksheet', 'Technician Worksheet'),
        ('technician_performance', 'Technician Performance'),
        ('technician_productivity', 'Technician Productivity'),
        ('team_performance', 'Team Performance'),
        ('overtime_report', 'Overtime Report'),
        ('service_request_summary', 'Service Request Summary'),
        ('service_request_detail', 'Service Request Detail'),
        ('labor_cost', 'Labor Cost'),
        ('materials_usage', 'Materials Usage'),
        ('customer_billing', 'Customer Billing'),
    ]
    
    report_type = serializers.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        required=True,
        help_text='Type of report to generate'
    )
    filters = serializers.DictField(
        required=False,
        default=dict,
        help_text='Filters to apply to the report (e.g., start_date, end_date, status)'
    )
    format = serializers.ChoiceField(
        choices=['json', 'pdf', 'excel'],
        default='json',
        required=False,
        help_text='Output format for the report'
    )
    use_cache = serializers.BooleanField(
        default=True,
        required=False,
        help_text='Whether to use cached report data if available'
    )
    
    def validate_report_type(self, value):
        """Validate that report type is registered."""
        from apps.reports.registry import registry
        
        if not registry.is_registered(value):
            raise serializers.ValidationError(f"Unknown report type: {value}")
        
        return value


class ReportTypeSerializer(serializers.Serializer):
    """
    Serializer for report type information.
    """
    report_type = serializers.CharField()
    report_name = serializers.CharField()
    description = serializers.CharField()
    generator_class = serializers.CharField()


class ReportTypeDetailSerializer(serializers.Serializer):
    """
    Serializer for detailed report type information.
    """
    report_type = serializers.CharField()
    report_name = serializers.CharField()
    description = serializers.CharField()
    generator_class = serializers.CharField()
    cache_ttl = serializers.IntegerField()
    available_filters = serializers.ListField(child=serializers.CharField())
