"""
Service Requests Models

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import UUIDPrimaryKeyMixin


class ServiceRequest(UUIDPrimaryKeyMixin, models.Model):
    """
    Customer-initiated service requests for equipment maintenance or issues.
    Customers can submit requests which are reviewed by admins/managers
    and optionally converted into tasks.
    """
    
    # Request Identification
    request_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique request number (e.g., REQ-2025-0001)"
    )
    
    # Relationships
    customer = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='service_requests',
        help_text="Customer who submitted the request"
    )
    equipment = models.ForeignKey(
        'equipment.Equipment',
        on_delete=models.CASCADE,
        related_name='service_requests',
        help_text="Equipment this request is for"
    )
    facility = models.ForeignKey(
        'facilities.Facility',
        on_delete=models.CASCADE,
        related_name='service_requests',
        help_text="Facility where equipment is located"
    )
    converted_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_request',
        help_text="Task created from this request"
    )
    
    # Request Details
    REQUEST_TYPE_CHOICES = [
        ('service', 'Service Request'),
        ('issue', 'Issue Report'),
        ('maintenance', 'Maintenance Request'),
        ('inspection', 'Inspection Request'),
    ]
    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        default='service',
        db_index=True,
        help_text="Type of request"
    )
    
    title = models.CharField(
        max_length=255,
        help_text="Brief title of the request"
    )
    description = models.TextField(
        help_text="Detailed description of the request or issue"
    )
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True,
        help_text="Priority level"
    )
    
    # Issue-specific fields
    ISSUE_TYPE_CHOICES = [
        ('breakdown', 'Equipment Breakdown'),
        ('malfunction', 'Malfunction'),
        ('safety', 'Safety Concern'),
        ('performance', 'Performance Issue'),
        ('other', 'Other'),
    ]
    issue_type = models.CharField(
        max_length=20,
        choices=ISSUE_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Type of issue (for issue reports)"
    )
    
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ]
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        null=True,
        blank=True,
        db_index=True,
        help_text="Severity level (for issue reports)"
    )
    
    # Status Tracking
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current status of the request"
    )
    
    # Admin Response
    reviewed_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        help_text="Admin/manager who reviewed the request"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was reviewed"
    )
    response_message = models.TextField(
        blank=True,
        help_text="Response message to customer"
    )
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated cost (not visible to customer)"
    )
    estimated_timeline = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estimated timeline for completion"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if rejected)"
    )
    
    # Internal Notes (not visible to customer)
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes for admin/manager use only"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the request was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the request was last updated"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the request was completed"
    )
    
    # Customer Feedback
    customer_rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Customer rating (1-5 stars)"
    )
    customer_feedback = models.TextField(
        blank=True,
        help_text="Customer feedback text"
    )
    feedback_submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When feedback was submitted"
    )
    
    class Meta:
        db_table = 'service_requests'
        verbose_name = 'Service Request'
        verbose_name_plural = 'Service Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['equipment', 'status']),
            models.Index(fields=['facility', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['created_at', 'status']),
        ]
    
    def __str__(self):
        return f"{self.request_number} - {self.title}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate customer role
        if self.customer and self.customer.role != 'customer':
            raise ValidationError({
                'customer': 'Only users with customer role can submit requests.'
            })
        
        # Validate issue-specific fields
        if self.request_type == 'issue':
            if not self.issue_type:
                raise ValidationError({
                    'issue_type': 'Issue type is required for issue reports.'
                })
            if not self.severity:
                raise ValidationError({
                    'severity': 'Severity is required for issue reports.'
                })
        
        # Validate rejection reason
        if self.status == 'rejected' and not self.rejection_reason:
            raise ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting a request.'
            })
        
        # Validate feedback
        if self.customer_rating and not (1 <= self.customer_rating <= 5):
            raise ValidationError({
                'customer_rating': 'Rating must be between 1 and 5.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to generate request number and run validation."""
        # Generate request number if not set
        if not self.request_number:
            self.request_number = self.generate_request_number()
        
        # Run validation
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_request_number():
        """Generate unique request number in format REQ-YYYY-NNNN."""
        from django.db.models import Max
        
        year = timezone.now().year
        prefix = f"REQ-{year}-"
        
        # Get the highest number for this year
        last_request = ServiceRequest.objects.filter(
            request_number__startswith=prefix
        ).aggregate(Max('request_number'))
        
        last_number = last_request['request_number__max']
        
        if last_number:
            # Extract the number part and increment
            last_num = int(last_number.split('-')[-1])
            new_num = last_num + 1
        else:
            # First request of the year
            new_num = 1
        
        return f"{prefix}{new_num:04d}"
    
    @property
    def is_pending(self):
        """Check if request is pending review."""
        return self.status == 'pending'
    
    @property
    def is_accepted(self):
        """Check if request is accepted."""
        return self.status == 'accepted'
    
    @property
    def is_rejected(self):
        """Check if request is rejected."""
        return self.status == 'rejected'
    
    @property
    def is_completed(self):
        """Check if request is completed."""
        return self.status == 'completed'
    
    @property
    def can_be_modified(self):
        """Check if request can be modified by customer."""
        return self.status in ['pending', 'under_review']
    
    @property
    def can_be_converted_to_task(self):
        """Check if request can be converted to task."""
        return self.status == 'accepted' and not self.converted_task
    
    def accept(self, reviewed_by, response_message='', estimated_timeline='', estimated_cost=None):
        """Accept the request."""
        self.status = 'accepted'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.response_message = response_message
        self.estimated_timeline = estimated_timeline
        if estimated_cost:
            self.estimated_cost = estimated_cost
        self.save()
    
    def reject(self, reviewed_by, rejection_reason):
        """Reject the request."""
        self.status = 'rejected'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.rejection_reason = rejection_reason
        self.save()
    
    def mark_under_review(self, reviewed_by):
        """Mark request as under review."""
        self.status = 'under_review'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()
    
    def mark_in_progress(self):
        """Mark request as in progress (when task is created)."""
        self.status = 'in_progress'
        self.save()
    
    def mark_completed(self):
        """Mark request as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def cancel(self):
        """Cancel the request."""
        if self.status not in ['pending', 'under_review']:
            raise ValidationError('Can only cancel pending or under review requests.')
        self.status = 'cancelled'
        self.save()
    
    def submit_feedback(self, rating, feedback_text=''):
        """Submit customer feedback."""
        if not self.is_completed:
            raise ValidationError('Can only submit feedback for completed requests.')
        
        self.customer_rating = rating
        self.customer_feedback = feedback_text
        self.feedback_submitted_at = timezone.now()
        self.save()


class RequestAction(UUIDPrimaryKeyMixin, models.Model):
    """
    Audit trail of all actions taken on service requests.
    Provides complete history and accountability.
    """
    
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='actions',
        help_text="Service request this action belongs to"
    )
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_actions',
        help_text="User who performed the action"
    )
    
    ACTION_TYPE_CHOICES = [
        ('created', 'Request Created'),
        ('reviewed', 'Under Review'),
        ('accepted', 'Request Accepted'),
        ('rejected', 'Request Rejected'),
        ('converted', 'Converted to Task'),
        ('updated', 'Request Updated'),
        ('commented', 'Comment Added'),
        ('completed', 'Request Completed'),
        ('cancelled', 'Request Cancelled'),
        ('feedback', 'Feedback Submitted'),
    ]
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        db_index=True,
        help_text="Type of action performed"
    )
    
    description = models.TextField(
        help_text="Description of the action"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the action"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the action was performed"
    )
    
    class Meta:
        db_table = 'request_actions'
        verbose_name = 'Request Action'
        verbose_name_plural = 'Request Actions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.request.request_number} - {self.get_action_type_display()}"
    
    @classmethod
    def log_action(cls, request, action_type, user=None, description='', metadata=None):
        """
        Log an action on a service request.
        
        Args:
            request: ServiceRequest instance
            action_type: Type of action (from ACTION_TYPE_CHOICES)
            user: User who performed the action (optional)
            description: Description of the action
            metadata: Additional metadata (dict)
        
        Returns:
            RequestAction instance
        """
        return cls.objects.create(
            request=request,
            user=user,
            action_type=action_type,
            description=description,
            metadata=metadata or {}
        )


class RequestComment(UUIDPrimaryKeyMixin, models.Model):
    """
    Comments and communication on service requests.
    Supports both customer-visible and internal comments.
    """
    
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='comments',
        help_text="Service request this comment belongs to"
    )
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_comments',
        help_text="User who posted the comment"
    )
    
    comment_text = models.TextField(
        help_text="Comment text"
    )
    is_internal = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this is an internal comment (not visible to customer)"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the comment was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the comment was last updated"
    )
    
    class Meta:
        db_table = 'request_comments'
        verbose_name = 'Request Comment'
        verbose_name_plural = 'Request Comments'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['request', 'created_at']),
            models.Index(fields=['request', 'is_internal']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        internal_flag = " (Internal)" if self.is_internal else ""
        return f"{self.request.request_number} - Comment by {self.user}{internal_flag}"
    
    def clean(self):
        """Validate comment data."""
        super().clean()
        
        # Validate that internal comments are only from admin/manager
        if self.is_internal and self.user:
            if self.user.role not in ['admin', 'manager']:
                raise ValidationError({
                    'is_internal': 'Only admins and managers can post internal comments.'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def create_system_comment(cls, request, comment_text, is_internal=False):
        """
        Create a system-generated comment.
        
        Args:
            request: ServiceRequest instance
            comment_text: Comment text
            is_internal: Whether this is an internal comment
        
        Returns:
            RequestComment instance
        """
        return cls.objects.create(
            request=request,
            user=None,  # System comment
            comment_text=comment_text,
            is_internal=is_internal
        )


class RequestAttachment(UUIDPrimaryKeyMixin, models.Model):
    """
    File attachments for service requests.
    Supports images and documents with size and type validation.
    """
    
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Service request this attachment belongs to"
    )
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_attachments',
        help_text="User who uploaded the file"
    )
    
    # File Information
    file = models.FileField(
        upload_to='service_requests/%Y/%m/',
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
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the file was uploaded"
    )
    
    class Meta:
        db_table = 'request_attachments'
        verbose_name = 'Request Attachment'
        verbose_name_plural = 'Request Attachments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request', 'created_at']),
            models.Index(fields=['uploaded_by', 'created_at']),
            models.Index(fields=['is_image']),
        ]
    
    def __str__(self):
        return f"{self.request.request_number} - {self.filename}"
    
    def clean(self):
        """Validate attachment data."""
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
        
        # Validate file type (whitelist)
        ALLOWED_TYPES = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ]
        if self.file_type not in ALLOWED_TYPES:
            raise ValidationError({
                'file': f'File type {self.file_type} is not allowed. Allowed types: images (JPG, PNG, GIF), PDF, Word documents.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
