"""
Files Models

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import os
from django.db import models
from django.core.validators import FileExtensionValidator
from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteModel


def user_file_upload_path(instance, filename):
    """Generate upload path for user files."""
    # Organize by user and date
    from datetime import datetime
    date_path = datetime.now().strftime('%Y/%m/%d')
    return f'user_files/{instance.uploaded_by.id}/{date_path}/{filename}'


class UserFile(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteModel):
    """
    User uploaded files that can be attached to various entities (tasks, service requests, etc.)
    or exist independently as user's file storage.
    """
    
    # File information
    file = models.FileField(
        upload_to=user_file_upload_path,
        max_length=500,
        help_text="Uploaded file"
    )
    filename = models.CharField(
        max_length=255,
        help_text="Original filename"
    )
    file_size = models.BigIntegerField(
        help_text="File size in bytes"
    )
    file_type = models.CharField(
        max_length=100,
        help_text="MIME type of the file"
    )
    
    # Metadata
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional title for the file"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for organizing files"
    )
    
    # Ownership
    uploaded_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='uploaded_files',
        help_text="User who uploaded the file"
    )
    
    # Optional attachments to entities
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_files',
        help_text="Optional task attachment"
    )
    service_request = models.ForeignKey(
        'service_requests.ServiceRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_files',
        help_text="Optional service request attachment"
    )
    
    # File properties
    is_image = models.BooleanField(
        default=False,
        help_text="Whether file is an image"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether file is publicly accessible"
    )
    
    class Meta:
        db_table = 'user_files'
        verbose_name = 'User File'
        verbose_name_plural = 'User Files'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by', '-created_at']),
            models.Index(fields=['task']),
            models.Index(fields=['service_request']),
            models.Index(fields=['file_type']),
            models.Index(fields=['is_image']),
        ]
    
    def __str__(self):
        return f"{self.filename} by {self.uploaded_by.full_name}"
    
    @property
    def file_extension(self):
        """Get file extension."""
        return os.path.splitext(self.filename)[1].lower()
    
    @property
    def file_size_mb(self):
        """Get file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def is_attached(self):
        """Check if file is attached to any entity."""
        return bool(self.task or self.service_request)
    
    def attach_to_task(self, task):
        """Attach file to a task."""
        self.task = task
        self.save(update_fields=['task', 'updated_at'])
    
    def attach_to_service_request(self, service_request):
        """Attach file to a service request."""
        self.service_request = service_request
        self.save(update_fields=['service_request', 'updated_at'])
    
    def detach(self):
        """Detach file from all entities."""
        self.task = None
        self.service_request = None
        self.save(update_fields=['task', 'service_request', 'updated_at'])
    
    def delete(self, *args, **kwargs):
        """Override delete to remove file from storage."""
        if self.file:
            # Delete the actual file
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)


class FileShare(UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Share files with other users or generate public links.
    """
    
    file = models.ForeignKey(
        UserFile,
        on_delete=models.CASCADE,
        related_name='shares',
        help_text="File being shared"
    )
    shared_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='shared_files',
        help_text="User who shared the file"
    )
    shared_with = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_files',
        help_text="User file is shared with (null for public links)"
    )
    
    # Share settings
    can_download = models.BooleanField(
        default=True,
        help_text="Whether recipient can download"
    )
    can_edit = models.BooleanField(
        default=False,
        help_text="Whether recipient can edit metadata"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When share link expires"
    )
    
    # Public link
    share_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Token for public share links"
    )
    
    # Tracking
    access_count = models.IntegerField(
        default=0,
        help_text="Number of times accessed"
    )
    last_accessed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last access time"
    )
    
    class Meta:
        db_table = 'file_shares'
        verbose_name = 'File Share'
        verbose_name_plural = 'File Shares'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file', 'shared_with']),
            models.Index(fields=['share_token']),
            models.Index(fields=['expires_at']),
        ]
        unique_together = [
            ['file', 'shared_with'],
        ]
    
    def __str__(self):
        if self.shared_with:
            return f"{self.file.filename} shared with {self.shared_with.full_name}"
        return f"{self.file.filename} - Public link"
    
    @property
    def is_expired(self):
        """Check if share has expired."""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_public(self):
        """Check if this is a public share."""
        return bool(self.share_token and not self.shared_with)
    
    def record_access(self):
        """Record an access to this share."""
        from django.utils import timezone
        self.access_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=['access_count', 'last_accessed_at'])
