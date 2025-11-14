"""
Reports Models

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from apps.core.models import SoftDeleteModel, AuditMixin, UUIDPrimaryKeyMixin


class ReportAuditLog(UUIDPrimaryKeyMixin, models.Model):
    """
    Audit trail for report generation.
    Tracks all report generation attempts, execution time, and results.
    """
    
    # User who generated the report
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports',
        help_text="User who generated the report"
    )
    
    # Report information
    report_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of report generated"
    )
    report_name = models.CharField(
        max_length=255,
        help_text="Human-readable report name"
    )
    
    # Filters and configuration
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters applied to the report"
    )
    
    # Format
    FORMAT_CHOICES = [
        ('json', 'JSON'),
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='json',
        db_index=True,
        help_text="Report output format"
    )
    
    # Execution details
    generated_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the report was generated"
    )
    execution_time = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Execution time in seconds"
    )
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Report generation status"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if generation failed"
    )
    
    # File information (for PDF/Excel exports)
    file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to generated file"
    )
    file_size = models.IntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    
    class Meta:
        db_table = 'report_audit_logs'
        verbose_name = 'Report Audit Log'
        verbose_name_plural = 'Report Audit Logs'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['user', 'generated_at']),
            models.Index(fields=['report_type', 'generated_at']),
            models.Index(fields=['status']),
            models.Index(fields=['format']),
        ]
    
    def __str__(self):
        user_name = self.user.full_name if self.user else 'System'
        return f"{self.report_name} by {user_name} at {self.generated_at}"
    
    @classmethod
    def log_report_generation(cls, user, report_type, report_name, filters, format='json'):
        """
        Create a new audit log entry for report generation.
        
        Args:
            user: User generating the report
            report_type: Type of report
            report_name: Human-readable report name
            filters: Filters applied
            format: Output format
            
        Returns:
            ReportAuditLog instance
        """
        return cls.objects.create(
            user=user,
            report_type=report_type,
            report_name=report_name,
            filters=filters,
            format=format,
            status='pending'
        )
    
    def mark_success(self, execution_time, file_path=None, file_size=None):
        """
        Mark report generation as successful.
        
        Args:
            execution_time: Time taken to generate report (seconds)
            file_path: Path to generated file (optional)
            file_size: Size of generated file (optional)
        """
        self.status = 'success'
        self.execution_time = execution_time
        if file_path:
            self.file_path = file_path
        if file_size:
            self.file_size = file_size
        self.save(update_fields=['status', 'execution_time', 'file_path', 'file_size'])
    
    def mark_failed(self, error_message):
        """
        Mark report generation as failed.
        
        Args:
            error_message: Error message describing the failure
        """
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])


class ReportSchedule(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Scheduled report configuration.
    Defines automated report generation and delivery.
    """
    
    # Basic information
    name = models.CharField(
        max_length=255,
        help_text="Schedule name"
    )
    report_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of report to generate"
    )
    
    # Report configuration
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters to apply to the report"
    )
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='pdf',
        help_text="Report output format"
    )
    
    # Scheduling configuration
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        help_text="How often to generate the report"
    )
    
    # For weekly schedules (0=Monday, 6=Sunday)
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of week for weekly schedules (0=Monday, 6=Sunday)"
    )
    
    # For monthly schedules (1-31)
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of month for monthly schedules (1-31)"
    )
    
    # Time of day to run
    time_of_day = models.TimeField(
        help_text="Time of day to generate the report"
    )
    
    # Recipients
    recipients = models.JSONField(
        default=list,
        help_text="List of email addresses to send the report to"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this schedule is active"
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the schedule last ran"
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the schedule will run next"
    )
    
    class Meta:
        db_table = 'report_schedules'
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'next_run']),
            models.Index(fields=['report_type']),
            models.Index(fields=['frequency']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def clean(self):
        """
        Validate schedule configuration.
        """
        super().clean()
        
        # Validate day_of_week for weekly schedules
        if self.frequency == 'weekly':
            if self.day_of_week is None:
                raise ValidationError({
                    'day_of_week': 'Day of week is required for weekly schedules.'
                })
            if not (0 <= self.day_of_week <= 6):
                raise ValidationError({
                    'day_of_week': 'Day of week must be between 0 (Monday) and 6 (Sunday).'
                })
        
        # Validate day_of_month for monthly schedules
        if self.frequency == 'monthly':
            if self.day_of_month is None:
                raise ValidationError({
                    'day_of_month': 'Day of month is required for monthly schedules.'
                })
            if not (1 <= self.day_of_month <= 31):
                raise ValidationError({
                    'day_of_month': 'Day of month must be between 1 and 31.'
                })
        
        # Validate recipients
        if not self.recipients or len(self.recipients) == 0:
            raise ValidationError({
                'recipients': 'At least one recipient email is required.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to calculate next_run and run validation.
        """
        self.full_clean()
        
        # Calculate next_run if not set
        if not self.next_run:
            self.next_run = self.calculate_next_run()
        
        super().save(*args, **kwargs)
    
    def calculate_next_run(self, from_date=None):
        """
        Calculate the next run time based on frequency and configuration.
        
        Args:
            from_date: Calculate from this date (default: now)
            
        Returns:
            datetime: Next run time
        """
        if from_date is None:
            from_date = timezone.now()
        
        # Combine date with time_of_day
        next_run = datetime.combine(from_date.date(), self.time_of_day)
        next_run = timezone.make_aware(next_run) if timezone.is_naive(next_run) else next_run
        
        if self.frequency == 'daily':
            # If time has passed today, schedule for tomorrow
            if next_run <= from_date:
                next_run += timedelta(days=1)
        
        elif self.frequency == 'weekly':
            # Find next occurrence of day_of_week
            days_ahead = self.day_of_week - from_date.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
        
        elif self.frequency == 'monthly':
            # Find next occurrence of day_of_month
            if from_date.day >= self.day_of_month:
                # Move to next month
                if from_date.month == 12:
                    next_run = next_run.replace(year=from_date.year + 1, month=1, day=self.day_of_month)
                else:
                    next_run = next_run.replace(month=from_date.month + 1, day=self.day_of_month)
            else:
                next_run = next_run.replace(day=self.day_of_month)
        
        return next_run
    
    def mark_executed(self):
        """
        Mark the schedule as executed and calculate next run time.
        """
        self.last_run = timezone.now()
        self.next_run = self.calculate_next_run(self.last_run)
        self.save(update_fields=['last_run', 'next_run'])
    
    @classmethod
    def get_due_schedules(cls):
        """
        Get all active schedules that are due to run.
        
        Returns:
            QuerySet of ReportSchedule instances
        """
        now = timezone.now()
        return cls.objects.filter(
            is_active=True,
            next_run__lte=now
        )
