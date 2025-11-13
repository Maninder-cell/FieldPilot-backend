"""
Service Requests Serializers

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import ServiceRequest, RequestAction, RequestComment, RequestAttachment
from apps.authentication.serializers import UserSerializer
from apps.equipment.serializers import EquipmentSerializer
from apps.facilities.serializers import FacilitySerializer


class RequestAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for request attachments.
    """
    uploaded_by = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = RequestAttachment
        fields = [
            'id', 'request', 'uploaded_by', 'file', 'file_url', 'filename',
            'file_size', 'file_type', 'is_image', 'created_at'
        ]
        read_only_fields = ['id', 'uploaded_by', 'file_size', 'file_type', 'is_image', 'created_at']
    
    def get_file_url(self, obj):
        """Get the file URL."""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def validate_file(self, value):
        """Validate file upload."""
        # Check file size
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size must not exceed {MAX_FILE_SIZE / (1024 * 1024)}MB.'
            )
        
        # Check file type
        ALLOWED_TYPES = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ]
        
        content_type = value.content_type
        if content_type not in ALLOWED_TYPES:
            raise serializers.ValidationError(
                'File type not allowed. Allowed types: images (JPG, PNG, GIF), PDF, Word documents.'
            )
        
        return value


class UploadAttachmentSerializer(serializers.Serializer):
    """
    Serializer for uploading attachments.
    """
    file = serializers.FileField()
    
    def validate_file(self, value):
        """Validate file upload."""
        # Check file size
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size must not exceed {MAX_FILE_SIZE / (1024 * 1024)}MB.'
            )
        
        # Check file type
        ALLOWED_TYPES = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ]
        
        content_type = value.content_type
        if content_type not in ALLOWED_TYPES:
            raise serializers.ValidationError(
                'File type not allowed. Allowed types: images (JPG, PNG, GIF), PDF, Word documents.'
            )
        
        return value


class RequestCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for request comments.
    """
    user = UserSerializer(read_only=True)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = RequestComment
        fields = [
            'id', 'request', 'user', 'user_name', 'comment_text',
            'is_internal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        """Get user's full name or 'System' for system comments."""
        if obj.user:
            return obj.user.full_name
        return 'System'
    
    def validate(self, data):
        """Validate comment data."""
        # Get user from context
        user = self.context.get('user')
        
        # Only admins/managers can post internal comments
        if data.get('is_internal', False):
            if not user or user.role not in ['admin', 'manager']:
                raise serializers.ValidationError({
                    'is_internal': 'Only admins and managers can post internal comments.'
                })
        
        return data


class CreateCommentSerializer(serializers.Serializer):
    """
    Serializer for creating comments.
    """
    comment_text = serializers.CharField()
    is_internal = serializers.BooleanField(default=False)
    
    def validate(self, data):
        """Validate comment data."""
        # Get user from context
        user = self.context.get('user')
        
        # Only admins/managers can post internal comments
        if data.get('is_internal', False):
            if not user or user.role not in ['admin', 'manager']:
                raise serializers.ValidationError({
                    'is_internal': 'Only admins and managers can post internal comments.'
                })
        
        return data


class RequestActionSerializer(serializers.ModelSerializer):
    """
    Serializer for request actions (audit trail).
    """
    user = UserSerializer(read_only=True)
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)
    
    class Meta:
        model = RequestAction
        fields = [
            'id', 'request', 'user', 'user_name', 'action_type',
            'action_display', 'description', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']
    
    def get_user_name(self, obj):
        """Get user's full name or 'System' for system actions."""
        if obj.user:
            return obj.user.full_name
        return 'System'


class ServiceRequestSerializer(serializers.ModelSerializer):
    """
    Full serializer for service requests (admin view).
    Includes all fields including internal notes.
    """
    customer = UserSerializer(read_only=True)
    equipment = EquipmentSerializer(read_only=True)
    facility = FacilitySerializer(read_only=True)
    reviewed_by = UserSerializer(read_only=True)
    converted_task = serializers.SerializerMethodField()
    
    # Related data
    attachments = RequestAttachmentSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    actions = RequestActionSerializer(many=True, read_only=True)
    
    # Display fields
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'request_number', 'customer', 'equipment', 'facility',
            'converted_task', 'request_type', 'request_type_display',
            'title', 'description', 'priority', 'priority_display',
            'issue_type', 'issue_type_display', 'severity', 'severity_display',
            'status', 'status_display', 'reviewed_by', 'reviewed_at',
            'response_message', 'estimated_cost', 'estimated_timeline',
            'rejection_reason', 'internal_notes', 'created_at', 'updated_at',
            'completed_at', 'customer_rating', 'customer_feedback',
            'feedback_submitted_at', 'attachments', 'comments', 'actions'
        ]
        read_only_fields = [
            'id', 'request_number', 'customer', 'reviewed_by', 'reviewed_at',
            'created_at', 'updated_at', 'completed_at', 'feedback_submitted_at'
        ]
    
    def get_converted_task(self, obj):
        """Get converted task details."""
        if obj.converted_task:
            return {
                'id': str(obj.converted_task.id),
                'task_number': obj.converted_task.task_number,
                'status': obj.converted_task.status,
                'status_display': obj.converted_task.get_status_display(),
            }
        return None
    
    def get_comments(self, obj):
        """Get all comments (including internal for admin)."""
        comments = obj.comments.all()
        return RequestCommentSerializer(comments, many=True, context=self.context).data


class CustomerServiceRequestSerializer(serializers.ModelSerializer):
    """
    Customer-facing serializer for service requests.
    Excludes internal fields like internal_notes and estimated_cost.
    """
    equipment = EquipmentSerializer(read_only=True)
    facility = FacilitySerializer(read_only=True)
    converted_task = serializers.SerializerMethodField()
    
    # Related data (filtered)
    attachments = RequestAttachmentSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    
    # Display fields
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'request_number', 'equipment', 'facility',
            'converted_task', 'request_type', 'request_type_display',
            'title', 'description', 'priority', 'priority_display',
            'issue_type', 'issue_type_display', 'severity', 'severity_display',
            'status', 'status_display', 'response_message',
            'estimated_timeline', 'rejection_reason', 'created_at',
            'updated_at', 'completed_at', 'customer_rating',
            'customer_feedback', 'feedback_submitted_at',
            'attachments', 'comments'
        ]
        read_only_fields = [
            'id', 'request_number', 'status', 'response_message',
            'estimated_timeline', 'rejection_reason', 'created_at',
            'updated_at', 'completed_at', 'feedback_submitted_at'
        ]
    
    def get_converted_task(self, obj):
        """Get converted task details (customer view)."""
        if obj.converted_task:
            task = obj.converted_task
            return {
                'id': str(task.id),
                'task_number': task.task_number,
                'status': task.status,
                'status_display': task.get_status_display(),
                'scheduled_start': task.scheduled_start,
                'scheduled_end': task.scheduled_end,
            }
        return None
    
    def get_comments(self, obj):
        """Get only non-internal comments for customer."""
        comments = obj.comments.filter(is_internal=False)
        return RequestCommentSerializer(comments, many=True, context=self.context).data


class CreateServiceRequestSerializer(serializers.Serializer):
    """
    Serializer for creating service requests.
    """
    equipment_id = serializers.UUIDField()
    request_type = serializers.ChoiceField(choices=ServiceRequest.REQUEST_TYPE_CHOICES)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    priority = serializers.ChoiceField(choices=ServiceRequest.PRIORITY_CHOICES, default='medium')
    
    # Issue-specific fields
    issue_type = serializers.ChoiceField(
        choices=ServiceRequest.ISSUE_TYPE_CHOICES,
        required=False,
        allow_null=True
    )
    severity = serializers.ChoiceField(
        choices=ServiceRequest.SEVERITY_CHOICES,
        required=False,
        allow_null=True
    )
    
    def validate(self, data):
        """Validate request data."""
        # If request type is 'issue', require issue_type and severity
        if data.get('request_type') == 'issue':
            if not data.get('issue_type'):
                raise serializers.ValidationError({
                    'issue_type': 'Issue type is required for issue reports.'
                })
            if not data.get('severity'):
                raise serializers.ValidationError({
                    'severity': 'Severity is required for issue reports.'
                })
        
        return data
    
    def validate_equipment_id(self, value):
        """Validate equipment exists and belongs to customer."""
        from apps.equipment.models import Equipment
        
        try:
            equipment = Equipment.objects.get(pk=value)
        except Equipment.DoesNotExist:
            raise serializers.ValidationError('Equipment not found.')
        
        # Check if equipment belongs to customer
        # customer in context is a User object, equipment.customer is a Customer object
        customer_user = self.context.get('customer')
        if customer_user:
            # Check if equipment has a customer assigned
            if not equipment.customer:
                raise serializers.ValidationError('This equipment is not assigned to any customer.')
            
            # Check if the equipment's customer is linked to the current user
            if equipment.customer.user != customer_user:
                raise serializers.ValidationError('You can only create requests for your own equipment.')
        
        return value


class UpdateServiceRequestSerializer(serializers.Serializer):
    """
    Serializer for updating service requests (customer).
    Only allows updating certain fields before review.
    """
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)
    priority = serializers.ChoiceField(choices=ServiceRequest.PRIORITY_CHOICES, required=False)
    issue_type = serializers.ChoiceField(choices=ServiceRequest.ISSUE_TYPE_CHOICES, required=False, allow_null=True)
    severity = serializers.ChoiceField(choices=ServiceRequest.SEVERITY_CHOICES, required=False, allow_null=True)


class AcceptRequestSerializer(serializers.Serializer):
    """
    Serializer for accepting service requests.
    """
    response_message = serializers.CharField(required=False, allow_blank=True)
    estimated_timeline = serializers.CharField(required=False, allow_blank=True)
    estimated_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )


class RejectRequestSerializer(serializers.Serializer):
    """
    Serializer for rejecting service requests.
    """
    rejection_reason = serializers.CharField()


class ConvertToTaskSerializer(serializers.Serializer):
    """
    Serializer for converting service requests to tasks.
    """
    assignee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    team_id = serializers.UUIDField(required=False, allow_null=True)
    scheduled_start = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end = serializers.DateTimeField(required=False, allow_null=True)
    priority = serializers.ChoiceField(
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
        required=False
    )


class SubmitFeedbackSerializer(serializers.Serializer):
    """
    Serializer for submitting customer feedback.
    """
    rating = serializers.IntegerField(min_value=1, max_value=5)
    feedback_text = serializers.CharField(required=False, allow_blank=True)


class UpdateInternalNotesSerializer(serializers.Serializer):
    """
    Serializer for updating internal notes.
    """
    internal_notes = serializers.CharField(allow_blank=True)
