"""
Tasks Models

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import SoftDeleteModel, AuditMixin, UUIDPrimaryKeyMixin, TimestampMixin


class TaskNumberSequence(models.Model):
    """
    Atomic counter for generating sequential task numbers.
    One sequence per tenant to ensure uniqueness within tenant schema.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_number = models.IntegerField(default=0, help_text="Last generated task number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'task_number_sequence'
        verbose_name = 'Task Number Sequence'
        verbose_name_plural = 'Task Number Sequences'
    
    def __str__(self):
        return f"Task Sequence - Last: {self.last_number}"
    
    @classmethod
    def generate_next_number(cls):
        """
        Generate the next task number in a thread-safe manner.
        Uses select_for_update to lock the row during transaction.
        
        Returns:
            str: Formatted task number (e.g., 'TASK-2025-000001')
        """
        with transaction.atomic():
            year = timezone.now().year
            
            # Get or create the sequence (there should only be one per tenant)
            sequence, created = cls.objects.select_for_update().get_or_create(
                pk=cls.objects.first().pk if cls.objects.exists() else uuid.uuid4(),
                defaults={'last_number': 0}
            )
            
            # Increment the counter
            sequence.last_number += 1
            next_number = sequence.last_number
            sequence.save(update_fields=['last_number', 'updated_at'])
            
            # Format as TASK-YYYY-NNNNNN (e.g., TASK-2025-000001)
            return f"TASK-{year}-{next_number:06d}"


class Task(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Main task model for equipment maintenance.
    Tasks are created by admins/managers and assigned to technicians or teams.
    """
    
    # Relationships
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text="Equipment this task is for"
    )
    
    # Basic Information
    task_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique task number (auto-generated)"
    )
    title = models.CharField(max_length=255, help_text="Task title")
    description = models.TextField(help_text="Detailed task description")
    
    # Administrative Status (set by admin/manager)
    STATUS_CHOICES = [
        ('new', 'New'),
        ('closed', 'Closed'),
        ('reopened', 'Re-Opened'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        db_index=True,
        help_text="Administrative status"
    )
    
    # Priority
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True,
        help_text="Task priority"
    )
    
    # Scheduling
    scheduled_start = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Scheduled start date/time"
    )
    scheduled_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled end date/time"
    )
    is_scheduled = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this task is scheduled for future"
    )
    
    # Material Tracking
    materials_needed = models.JSONField(
        default=list,
        blank=True,
        help_text="List of materials needed for this task"
    )
    materials_received = models.JSONField(
        default=list,
        blank=True,
        help_text="List of materials received"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes")
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for additional data"
    )
    
    class Meta:
        db_table = 'tasks'
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_number']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['equipment', 'status']),
            models.Index(fields=['scheduled_start']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_scheduled']),
        ]
    
    def __str__(self):
        return f"{self.task_number} - {self.title}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate scheduled dates
        if self.scheduled_start and self.scheduled_end:
            if self.scheduled_end <= self.scheduled_start:
                raise ValidationError({
                    'scheduled_end': 'Scheduled end must be after scheduled start.'
                })
        
        # Set is_scheduled flag
        if self.scheduled_start and self.scheduled_start > timezone.now():
            self.is_scheduled = True
        else:
            self.is_scheduled = False
    
    def save(self, *args, **kwargs):
        """
        Override save to generate task number and run validation.
        """
        # Generate task number if not provided
        if not self.task_number:
            self.task_number = TaskNumberSequence.generate_next_number()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if task is active (not closed, rejected, or deleted)."""
        return self.status not in ['closed', 'rejected'] and not self.is_deleted
    
    @property
    def is_visible_to_technicians(self):
        """Check if task should be visible to technicians."""
        if self.is_deleted:
            return False
        if self.is_scheduled and self.scheduled_start > timezone.now():
            return False
        return True
    
    @property
    def facility(self):
        """Get the facility this task's equipment belongs to."""
        return self.equipment.building.facility if self.equipment else None


class TechnicianTeam(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Team of technicians for group task assignments.
    Only users with role='technician' can be team members.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Team name"
    )
    description = models.TextField(blank=True, help_text="Team description")
    
    # Members
    members = models.ManyToManyField(
        'authentication.User',
        related_name='technician_teams',
        limit_choices_to={'role': 'technician'},
        help_text="Team members (technicians only)"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether team is active"
    )
    
    class Meta:
        db_table = 'technician_teams'
        verbose_name = 'Technician Team'
        verbose_name_plural = 'Technician Teams'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate name is unique among non-deleted teams
        if self.name:
            existing = TechnicianTeam.objects.filter(
                name=self.name
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError({
                    'name': 'A team with this name already exists.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def member_count(self):
        """Get count of team members."""
        return self.members.count()
    
    @property
    def active_member_count(self):
        """Get count of active team members."""
        return self.members.filter(is_active=True).count()


class TaskAssignment(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Assignment of a task to a technician or team.
    Tracks individual work status per assignee.
    Either assignee OR team must be set, not both.
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='assignments',
        help_text="Task being assigned"
    )
    assignee = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_assignments',
        limit_choices_to={'role': 'technician'},
        help_text="Individual technician assigned"
    )
    team = models.ForeignKey(
        TechnicianTeam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='task_assignments',
        help_text="Team assigned"
    )
    
    # Work Status (updated by technician)
    WORK_STATUS_CHOICES = [
        ('open', 'Open'),
        ('hold', 'Hold'),
        ('in_progress', 'In-Progress'),
        ('done', 'Done'),
    ]
    work_status = models.CharField(
        max_length=20,
        choices=WORK_STATUS_CHOICES,
        default='open',
        db_index=True,
        help_text="Work status (updated by technician)"
    )
    
    # Assignment Metadata
    assigned_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_assignments_made',
        help_text="User who made the assignment"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'task_assignments'
        verbose_name = 'Task Assignment'
        verbose_name_plural = 'Task Assignments'
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['task', 'assignee']),
            models.Index(fields=['task', 'team']),
            models.Index(fields=['work_status']),
            models.Index(fields=['assignee', 'work_status']),
        ]
        # Ensure a task is not assigned to the same technician/team multiple times
        unique_together = [
            ['task', 'assignee'],
            ['task', 'team'],
        ]
    
    def __str__(self):
        if self.assignee:
            return f"{self.task.task_number} → {self.assignee.full_name}"
        elif self.team:
            return f"{self.task.task_number} → Team: {self.team.name}"
        return f"{self.task.task_number} → Unassigned"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Ensure either assignee OR team is set, not both
        if self.assignee and self.team:
            raise ValidationError(
                "Cannot assign to both individual technician and team. Choose one."
            )
        
        if not self.assignee and not self.team:
            raise ValidationError(
                "Must assign to either an individual technician or a team."
            )
        
        # Validate assignee is a technician
        if self.assignee and self.assignee.role != 'technician':
            raise ValidationError({
                'assignee': 'Only technicians can be assigned to tasks.'
            })
        
        # Validate team is active
        if self.team and not self.team.is_active:
            raise ValidationError({
                'team': 'Cannot assign to an inactive team.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def assignee_name(self):
        """Get the name of the assignee (technician or team)."""
        if self.assignee:
            return self.assignee.full_name
        elif self.team:
            return f"Team: {self.team.name}"
        return "Unassigned"



class TimeLog(UUIDPrimaryKeyMixin, models.Model):
    """
    Time tracking for technician site visits.
    Tracks travel, arrival, departure, and lunch breaks.
    Calculates work hours, normal hours, and overtime.
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='time_logs',
        help_text="Task being worked on"
    )
    technician = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='time_logs',
        limit_choices_to={'role': 'technician'},
        help_text="Technician performing the work"
    )
    
    # Time Tracking
    travel_started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When technician started traveling to site"
    )
    arrived_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When technician arrived at site"
    )
    departed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When technician departed from site"
    )
    
    # Lunch Breaks
    lunch_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When lunch break started"
    )
    lunch_ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When lunch break ended"
    )
    
    # Equipment Status at Departure
    EQUIPMENT_STATUS_CHOICES = [
        ('functional', 'Functional'),
        ('shutdown', 'Shutdown'),
    ]
    equipment_status_at_departure = models.CharField(
        max_length=20,
        choices=EQUIPMENT_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Equipment status when technician departed"
    )
    
    # Calculated Fields (updated on departure)
    total_work_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Total work hours (arrival to departure minus lunch)"
    )
    normal_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Normal work hours (up to 8 hours)"
    )
    overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Overtime hours (beyond 8 hours)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'time_logs'
        verbose_name = 'Time Log'
        verbose_name_plural = 'Time Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'technician']),
            models.Index(fields=['technician', 'departed_at']),
            models.Index(fields=['arrived_at', 'departed_at']),
            models.Index(fields=['travel_started_at']),
            models.Index(fields=['task', 'technician', 'departed_at']),  # For finding active logs
        ]
        # Allow multiple time logs per technician per task (multiple visits)
        # No unique_together constraint
    
    def __str__(self):
        return f"{self.technician.full_name} - {self.task.task_number}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate technician role
        if self.technician and self.technician.role != 'technician':
            raise ValidationError({
                'technician': 'Only technicians can have time logs.'
            })
        
        # Validate time sequence
        if self.travel_started_at and self.arrived_at:
            if self.arrived_at < self.travel_started_at:
                raise ValidationError({
                    'arrived_at': 'Arrival time must be after travel start time.'
                })
        
        if self.arrived_at and self.departed_at:
            if self.departed_at < self.arrived_at:
                raise ValidationError({
                    'departed_at': 'Departure time must be after arrival time.'
                })
            
            # Warn about unreasonably long work sessions (more than 24 hours)
            time_diff = self.departed_at - self.arrived_at
            hours_diff = time_diff.total_seconds() / 3600
            if hours_diff > 24:
                # This is a warning, not an error - allow it but log it
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"TimeLog for task {self.task.task_number}: "
                    f"Work session exceeds 24 hours ({hours_diff:.2f} hours). "
                    f"Arrived: {self.arrived_at}, Departed: {self.departed_at}"
                )
        
        # Validate lunch times
        if self.lunch_started_at and self.lunch_ended_at:
            if self.lunch_ended_at <= self.lunch_started_at:
                raise ValidationError({
                    'lunch_ended_at': 'Lunch end time must be after lunch start time.'
                })
            
            # Lunch must be during work hours
            if self.arrived_at and self.lunch_started_at < self.arrived_at:
                raise ValidationError({
                    'lunch_started_at': 'Lunch cannot start before arrival.'
                })
            
            if self.departed_at and self.lunch_ended_at > self.departed_at:
                raise ValidationError({
                    'lunch_ended_at': 'Lunch cannot end after departure.'
                })
        
        # Validate lunch is not started without ending
        if self.lunch_started_at and not self.lunch_ended_at:
            # Check if this is a new lunch start (not an update)
            if self.pk:
                old_instance = TimeLog.objects.get(pk=self.pk)
                if old_instance.lunch_started_at == self.lunch_started_at:
                    # This is an update, not a new lunch start
                    pass
        
        # Validate equipment status is provided on departure
        if self.departed_at and not self.equipment_status_at_departure:
            raise ValidationError({
                'equipment_status_at_departure': 'Equipment status is required when departing.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation and calculate work hours.
        """
        # Calculate work hours BEFORE validation if departed
        if self.arrived_at and self.departed_at:
            self.calculate_work_hours()
        
        # Now validate with calculated values
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    def calculate_work_hours(self):
        """
        Calculate total work hours, normal hours, and overtime.
        Called automatically on save when both arrived_at and departed_at are set.
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        if not self.arrived_at or not self.departed_at:
            return
        
        # Calculate total time
        total_time = self.departed_at - self.arrived_at
        
        # Subtract lunch break if applicable
        if self.lunch_started_at and self.lunch_ended_at:
            lunch_duration = self.lunch_ended_at - self.lunch_started_at
            total_time -= lunch_duration
        
        # Convert to hours
        total_hours = total_time.total_seconds() / 3600
        
        # Cap at reasonable maximum (720 hours = 30 days * 24 hours)
        # This prevents database overflow while allowing for edge cases
        MAX_HOURS = 720
        if total_hours > MAX_HOURS:
            total_hours = MAX_HOURS
        
        # Calculate normal vs overtime (8 hours per day is normal)
        NORMAL_HOURS_PER_DAY = 8
        normal_hours = min(total_hours, NORMAL_HOURS_PER_DAY)
        overtime_hours = max(0, total_hours - NORMAL_HOURS_PER_DAY)
        
        # Update fields with proper Decimal precision (2 decimal places)
        self.total_work_hours = Decimal(str(total_hours)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.normal_hours = Decimal(str(normal_hours)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.overtime_hours = Decimal(str(overtime_hours)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def is_on_site(self):
        """Check if technician is currently on site."""
        return self.arrived_at is not None and self.departed_at is None
    
    @property
    def is_traveling(self):
        """Check if technician is currently traveling."""
        return self.travel_started_at is not None and self.arrived_at is None
    
    @property
    def is_on_lunch(self):
        """Check if technician is currently on lunch break."""
        return self.lunch_started_at is not None and self.lunch_ended_at is None
    
    @property
    def can_start_lunch(self):
        """Check if technician can start lunch break."""
        return self.is_on_site and not self.is_on_lunch
    
    @classmethod
    def get_active_log(cls, task, technician):
        """
        Get the active (not yet departed) time log for a technician on a task.
        Returns None if no active log exists.
        """
        return cls.objects.filter(
            task=task,
            technician=technician,
            departed_at__isnull=True
        ).order_by('-created_at').first()
    
    @classmethod
    def get_or_create_active_log(cls, task, technician):
        """
        Get the active time log or create a new one if none exists.
        Returns (time_log, created) tuple.
        """
        active_log = cls.get_active_log(task, technician)
        if active_log:
            return active_log, False
        else:
            new_log = cls.objects.create(task=task, technician=technician)
            return new_log, True
    
    @property
    def can_end_lunch(self):
        """Check if technician can end lunch break."""
        return self.is_on_lunch
    
    @classmethod
    def get_active_log_for_technician(cls, technician):
        """
        Get the active time log for a technician (if any).
        Active means technician has not departed yet.
        """
        return cls.objects.filter(
            technician=technician,
            departed_at__isnull=True
        ).first()
    
    @classmethod
    def can_technician_travel(cls, technician, exclude_task=None):
        """
        Check if technician can travel to a new site.
        Returns (can_travel: bool, message: str)
        """
        query = cls.objects.filter(
            technician=technician,
            departed_at__isnull=True
        )
        
        if exclude_task:
            query = query.exclude(task=exclude_task)
        
        active_log = query.first()
        
        if active_log:
            return False, f"Technician is already at site for task {active_log.task.task_number}"
        
        return True, None


class TaskComment(UUIDPrimaryKeyMixin, models.Model):
    """
    Comments on tasks for communication between team members.
    Can be user-generated or system-generated (automatic comments).
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text="Task this comment belongs to"
    )
    author = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_comments',
        help_text="User who wrote the comment"
    )
    
    # Content
    comment = models.TextField(help_text="Comment text")
    is_system_generated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is an automatic system comment"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'task_comments'
        verbose_name = 'Task Comment'
        verbose_name_plural = 'Task Comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['is_system_generated']),
        ]
    
    def __str__(self):
        author_name = self.author.full_name if self.author else "System"
        return f"{author_name} on {self.task.task_number}"
    
    @classmethod
    def create_system_comment(cls, task, comment_text):
        """
        Create a system-generated comment.
        """
        return cls.objects.create(
            task=task,
            comment=comment_text,
            is_system_generated=True
        )


class TaskAttachment(UUIDPrimaryKeyMixin, models.Model):
    """
    File attachments for tasks (images, documents, etc.).
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Task this attachment belongs to"
    )
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_attachments',
        help_text="User who uploaded the file"
    )
    
    # File Information
    file = models.FileField(
        upload_to='task_attachments/%Y/%m/',
        help_text="Uploaded file"
    )
    filename = models.CharField(
        max_length=255,
        help_text="Original filename"
    )
    file_size = models.IntegerField(
        help_text="File size in bytes"
    )
    file_type = models.CharField(
        max_length=100,
        help_text="MIME type"
    )
    is_image = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether file is an image"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'task_attachments'
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['is_image']),
        ]
    
    def __str__(self):
        return f"{self.filename} - {self.task.task_number}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate file size (10MB max)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
        if self.file_size > MAX_FILE_SIZE:
            raise ValidationError({
                'file': f'File size must not exceed {MAX_FILE_SIZE / (1024 * 1024)}MB.'
            })
        
        # Set is_image flag based on MIME type
        if self.file_type and self.file_type.startswith('image/'):
            self.is_image = True
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)


class TaskHistory(UUIDPrimaryKeyMixin, models.Model):
    """
    Complete audit trail for all task changes and actions.
    Records every modification, status change, and action taken on a task.
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="Task this history entry belongs to"
    )
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_history',
        help_text="User who performed the action"
    )
    
    # Action Information
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('status_changed', 'Status Changed'),
        ('priority_changed', 'Priority Changed'),
        ('assigned', 'Assigned'),
        ('work_status_changed', 'Work Status Changed'),
        ('comment_added', 'Comment Added'),
        ('file_uploaded', 'File Uploaded'),
        ('travel_started', 'Travel Started'),
        ('arrived', 'Arrived'),
        ('departed', 'Departed'),
        ('lunch_started', 'Lunch Started'),
        ('lunch_ended', 'Lunch Ended'),
        ('material_needed', 'Material Needed'),
        ('material_received', 'Material Received'),
    ]
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True,
        help_text="Type of action performed"
    )
    
    # Change Details
    field_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Field that was changed (if applicable)"
    )
    old_value = models.TextField(
        blank=True,
        help_text="Previous value (if applicable)"
    )
    new_value = models.TextField(
        blank=True,
        help_text="New value (if applicable)"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context and details"
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'task_history'
        verbose_name = 'Task History'
        verbose_name_plural = 'Task History'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        user_name = self.user.full_name if self.user else "System"
        return f"{self.task.task_number} - {self.action} by {user_name}"
    
    @classmethod
    def log_action(cls, task, action, user=None, field_name='', old_value='', new_value='', details=None):
        """
        Create a history entry for an action.
        
        Args:
            task: Task instance
            action: Action type (from ACTION_CHOICES)
            user: User who performed the action (optional)
            field_name: Name of field that changed (optional)
            old_value: Previous value (optional)
            new_value: New value (optional)
            details: Additional context dict (optional)
        """
        return cls.objects.create(
            task=task,
            user=user,
            action=action,
            field_name=field_name,
            old_value=str(old_value) if old_value else '',
            new_value=str(new_value) if new_value else '',
            details=details or {}
        )


class MaterialLog(UUIDPrimaryKeyMixin, models.Model):
    """
    Tracks materials needed and received for tasks.
    Provides detailed tracking of resource requirements and usage.
    """
    
    # Relationships
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='material_logs',
        help_text="Task this material log belongs to"
    )
    logged_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='material_logs',
        help_text="User who logged the material"
    )
    
    # Log Type
    LOG_TYPE_CHOICES = [
        ('needed', 'Needed'),
        ('received', 'Received'),
    ]
    log_type = models.CharField(
        max_length=20,
        choices=LOG_TYPE_CHOICES,
        db_index=True,
        help_text="Whether material is needed or received"
    )
    
    # Material Information
    material_name = models.CharField(
        max_length=255,
        help_text="Name of the material"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Quantity of material"
    )
    unit = models.CharField(
        max_length=50,
        help_text="Unit of measurement (e.g., pieces, kg, liters)"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the material"
    )
    
    # Timestamp
    logged_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'material_logs'
        verbose_name = 'Material Log'
        verbose_name_plural = 'Material Logs'
        ordering = ['-logged_at']
        indexes = [
            models.Index(fields=['task', 'log_type']),
            models.Index(fields=['log_type']),
            models.Index(fields=['logged_at']),
        ]
    
    def __str__(self):
        return f"{self.material_name} ({self.quantity} {self.unit}) - {self.log_type}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate quantity is positive
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be greater than zero.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
