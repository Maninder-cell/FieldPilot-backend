"""
Service Requests Admin Interface

Task 23: Create admin interface
Django admin configuration for service request models.

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import ServiceRequest, RequestAction, RequestComment, RequestAttachment


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    """Admin interface for ServiceRequest model."""
    
    list_display = [
        'request_number',
        'customer_link',
        'equipment_link',
        'request_type',
        'priority',
        'status',
        'created_at',
        'actions_column'
    ]
    
    list_filter = [
        'status',
        'priority',
        'request_type',
        'severity',
        'created_at',
    ]
    
    search_fields = [
        'request_number',
        'title',
        'description',
        'customer__email',
        'customer__first_name',
        'customer__last_name',
        'equipment__name',
    ]
    
    readonly_fields = [
        'id',
        'request_number',
        'created_at',
        'updated_at',
        'reviewed_at',
        'completed_at',
        'feedback_submitted_at',
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id',
                'request_number',
                'customer',
                'equipment',
                'facility',
            )
        }),
        ('Request Details', {
            'fields': (
                'request_type',
                'title',
                'description',
                'priority',
            )
        }),
        ('Issue Details (for issue reports)', {
            'fields': (
                'issue_type',
                'severity',
            ),
            'classes': ('collapse',),
        }),
        ('Status & Review', {
            'fields': (
                'status',
                'reviewed_by',
                'reviewed_at',
                'response_message',
                'estimated_timeline',
                'estimated_cost',
                'rejection_reason',
            )
        }),
        ('Internal', {
            'fields': (
                'internal_notes',
            ),
            'classes': ('collapse',),
        }),
        ('Task Conversion', {
            'fields': (
                'converted_task',
            )
        }),
        ('Customer Feedback', {
            'fields': (
                'customer_rating',
                'customer_feedback',
                'feedback_submitted_at',
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'completed_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'mark_under_review',
        'mark_accepted',
        'mark_completed',
        'export_to_csv',
    ]
    
    def customer_link(self, obj):
        """Display customer as clickable link."""
        if obj.customer:
            url = reverse('admin:authentication_user_change', args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', url, obj.customer.get_full_name())
        return '-'
    customer_link.short_description = 'Customer'
    
    def equipment_link(self, obj):
        """Display equipment as clickable link."""
        if obj.equipment:
            url = reverse('admin:equipment_equipment_change', args=[obj.equipment.id])
            return format_html('<a href="{}">{}</a>', url, obj.equipment.name)
        return '-'
    equipment_link.short_description = 'Equipment'
    
    def actions_column(self, obj):
        """Display quick action buttons."""
        buttons = []
        
        if obj.status == 'pending':
            buttons.append(
                format_html(
                    '<a class="button" href="{}">Review</a>',
                    reverse('admin:service_requests_servicerequest_change', args=[obj.id])
                )
            )
        
        if obj.status == 'accepted' and not obj.converted_task:
            buttons.append(
                format_html(
                    '<a class="button" href="{}">Convert to Task</a>',
                    reverse('admin:service_requests_servicerequest_change', args=[obj.id])
                )
            )
        
        return format_html(' '.join(buttons)) if buttons else '-'
    actions_column.short_description = 'Actions'
    
    def mark_under_review(self, request, queryset):
        """Bulk action to mark requests as under review."""
        updated = 0
        for obj in queryset.filter(status='pending'):
            obj.mark_under_review(request.user)
            RequestAction.log_action(
                request=obj,
                action_type='reviewed',
                user=request.user,
                description=f'Marked under review by {request.user.get_full_name()}'
            )
            updated += 1
        
        self.message_user(request, f'{updated} request(s) marked as under review.')
    mark_under_review.short_description = 'Mark selected as under review'
    
    def mark_accepted(self, request, queryset):
        """Bulk action to accept requests."""
        updated = 0
        for obj in queryset.filter(status__in=['pending', 'under_review']):
            obj.accept(
                reviewed_by=request.user,
                response_message='Request accepted via bulk action'
            )
            RequestAction.log_action(
                request=obj,
                action_type='accepted',
                user=request.user,
                description=f'Accepted by {request.user.get_full_name()}'
            )
            updated += 1
        
        self.message_user(request, f'{updated} request(s) accepted.')
    mark_accepted.short_description = 'Accept selected requests'
    
    def mark_completed(self, request, queryset):
        """Bulk action to mark requests as completed."""
        updated = 0
        for obj in queryset.filter(status='in_progress'):
            obj.mark_completed()
            RequestAction.log_action(
                request=obj,
                action_type='completed',
                user=request.user,
                description=f'Marked completed by {request.user.get_full_name()}'
            )
            updated += 1
        
        self.message_user(request, f'{updated} request(s) marked as completed.')
    mark_completed.short_description = 'Mark selected as completed'
    
    def export_to_csv(self, request, queryset):
        """Export selected requests to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="service_requests.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Request Number', 'Customer', 'Equipment', 'Type', 'Priority',
            'Status', 'Created', 'Completed'
        ])
        
        for obj in queryset:
            writer.writerow([
                obj.request_number,
                obj.customer.get_full_name() if obj.customer else '',
                obj.equipment.name if obj.equipment else '',
                obj.get_request_type_display(),
                obj.get_priority_display(),
                obj.get_status_display(),
                obj.created_at.strftime('%Y-%m-%d %H:%M'),
                obj.completed_at.strftime('%Y-%m-%d %H:%M') if obj.completed_at else '',
            ])
        
        return response
    export_to_csv.short_description = 'Export selected to CSV'


@admin.register(RequestAction)
class RequestActionAdmin(admin.ModelAdmin):
    """Admin interface for RequestAction model."""
    
    list_display = [
        'request_number',
        'action_type',
        'user_name',
        'created_at',
    ]
    
    list_filter = [
        'action_type',
        'created_at',
    ]
    
    search_fields = [
        'request__request_number',
        'description',
        'user__email',
    ]
    
    readonly_fields = [
        'id',
        'request',
        'user',
        'action_type',
        'description',
        'metadata',
        'created_at',
    ]
    
    def request_number(self, obj):
        """Display request number."""
        return obj.request.request_number
    request_number.short_description = 'Request'
    
    def user_name(self, obj):
        """Display user name."""
        return obj.user.get_full_name() if obj.user else 'System'
    user_name.short_description = 'User'
    
    def has_add_permission(self, request):
        """Disable manual creation of actions."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deletion of actions (audit trail)."""
        return False


@admin.register(RequestComment)
class RequestCommentAdmin(admin.ModelAdmin):
    """Admin interface for RequestComment model."""
    
    list_display = [
        'request_number',
        'user_name',
        'comment_preview',
        'is_internal',
        'created_at',
    ]
    
    list_filter = [
        'is_internal',
        'created_at',
    ]
    
    search_fields = [
        'request__request_number',
        'comment_text',
        'user__email',
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Comment Details', {
            'fields': (
                'id',
                'request',
                'user',
                'comment_text',
                'is_internal',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def request_number(self, obj):
        """Display request number."""
        return obj.request.request_number
    request_number.short_description = 'Request'
    
    def user_name(self, obj):
        """Display user name."""
        return obj.user.get_full_name() if obj.user else 'System'
    user_name.short_description = 'User'
    
    def comment_preview(self, obj):
        """Display comment preview."""
        return obj.comment_text[:50] + '...' if len(obj.comment_text) > 50 else obj.comment_text
    comment_preview.short_description = 'Comment'


@admin.register(RequestAttachment)
class RequestAttachmentAdmin(admin.ModelAdmin):
    """Admin interface for RequestAttachment model."""
    
    list_display = [
        'request_number',
        'filename',
        'file_type',
        'file_size_display',
        'is_image',
        'uploaded_by_name',
        'created_at',
    ]
    
    list_filter = [
        'is_image',
        'file_type',
        'created_at',
    ]
    
    search_fields = [
        'request__request_number',
        'filename',
        'uploaded_by__email',
    ]
    
    readonly_fields = [
        'id',
        'file_size',
        'file_type',
        'is_image',
        'created_at',
    ]
    
    fieldsets = (
        ('Attachment Details', {
            'fields': (
                'id',
                'request',
                'uploaded_by',
                'file',
                'filename',
            )
        }),
        ('File Information', {
            'fields': (
                'file_size',
                'file_type',
                'is_image',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def request_number(self, obj):
        """Display request number."""
        return obj.request.request_number
    request_number.short_description = 'Request'
    
    def uploaded_by_name(self, obj):
        """Display uploader name."""
        return obj.uploaded_by.get_full_name() if obj.uploaded_by else '-'
    uploaded_by_name.short_description = 'Uploaded By'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = 'File Size'
