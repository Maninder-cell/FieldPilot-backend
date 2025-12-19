"""
Files Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import UserFile, FileShare


class UserFileSerializer(serializers.ModelSerializer):
    """Serializer for user files."""
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    file_extension = serializers.ReadOnlyField()
    is_attached = serializers.ReadOnlyField()
    task_number = serializers.CharField(source='task.task_number', read_only=True, allow_null=True)
    service_request_number = serializers.CharField(source='service_request.request_number', read_only=True, allow_null=True)
    
    class Meta:
        model = UserFile
        fields = [
            'id', 'file', 'file_url', 'filename', 'file_size', 'file_size_mb',
            'file_type', 'file_extension', 'title', 'description', 'tags',
            'uploaded_by', 'uploaded_by_name', 'task', 'task_number',
            'service_request', 'service_request_number', 'is_image', 'is_public',
            'is_attached', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'uploaded_by_name', 'file_size', 'file_type',
            'is_image', 'created_at', 'updated_at'
        ]
    
    def get_file_url(self, obj):
        """Get file URL."""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class UploadFileSerializer(serializers.Serializer):
    """Serializer for uploading files."""
    
    file = serializers.FileField(required=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True
    )
    is_public = serializers.BooleanField(default=False, required=False)
    task_id = serializers.UUIDField(required=False, allow_null=True)
    service_request_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate_file(self, value):
        """Validate file size."""
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(f"File size cannot exceed 50MB. Current size: {round(value.size / (1024 * 1024), 2)}MB")
        return value
    
    def validate(self, data):
        """Validate that task or service_request exists if provided."""
        task_id = data.get('task_id')
        service_request_id = data.get('service_request_id')
        
        if task_id:
            from apps.tasks.models import Task
            if not Task.objects.filter(pk=task_id).exists():
                raise serializers.ValidationError({'task_id': 'Task not found'})
        
        if service_request_id:
            from apps.service_requests.models import ServiceRequest
            if not ServiceRequest.objects.filter(pk=service_request_id).exists():
                raise serializers.ValidationError({'service_request_id': 'Service request not found'})
        
        return data


class UpdateFileSerializer(serializers.ModelSerializer):
    """Serializer for updating file metadata."""
    
    class Meta:
        model = UserFile
        fields = ['title', 'description', 'tags', 'is_public']


class AttachFileSerializer(serializers.Serializer):
    """Serializer for attaching file to entities."""
    
    task_id = serializers.UUIDField(required=False, allow_null=True)
    service_request_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate that at least one entity is provided."""
        task_id = data.get('task_id')
        service_request_id = data.get('service_request_id')
        
        if not task_id and not service_request_id:
            raise serializers.ValidationError("Must provide either task_id or service_request_id")
        
        if task_id and service_request_id:
            raise serializers.ValidationError("Cannot attach to both task and service request")
        
        if task_id:
            from apps.tasks.models import Task
            if not Task.objects.filter(pk=task_id).exists():
                raise serializers.ValidationError({'task_id': 'Task not found'})
        
        if service_request_id:
            from apps.service_requests.models import ServiceRequest
            if not ServiceRequest.objects.filter(pk=service_request_id).exists():
                raise serializers.ValidationError({'service_request_id': 'Service request not found'})
        
        return data


class FileShareSerializer(serializers.ModelSerializer):
    """Serializer for file shares."""
    
    file_name = serializers.CharField(source='file.filename', read_only=True)
    shared_by_name = serializers.CharField(source='shared_by.full_name', read_only=True)
    shared_with_name = serializers.CharField(source='shared_with.full_name', read_only=True, allow_null=True)
    is_expired = serializers.ReadOnlyField()
    is_public = serializers.ReadOnlyField()
    share_url = serializers.SerializerMethodField()
    
    class Meta:
        model = FileShare
        fields = [
            'id', 'file', 'file_name', 'shared_by', 'shared_by_name',
            'shared_with', 'shared_with_name', 'can_download', 'can_edit',
            'expires_at', 'share_token', 'share_url', 'access_count',
            'last_accessed_at', 'is_expired', 'is_public', 'created_at'
        ]
        read_only_fields = [
            'id', 'shared_by', 'share_token', 'access_count',
            'last_accessed_at', 'created_at'
        ]
    
    def get_share_url(self, obj):
        """Get share URL."""
        if obj.share_token:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/api/v1/files/shared/{obj.share_token}/')
        return None


class CreateFileShareSerializer(serializers.Serializer):
    """Serializer for creating file shares."""
    
    file_id = serializers.UUIDField(required=True)
    shared_with_id = serializers.UUIDField(required=False, allow_null=True)
    can_download = serializers.BooleanField(default=True)
    can_edit = serializers.BooleanField(default=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    generate_public_link = serializers.BooleanField(default=False)
    
    def validate_file_id(self, value):
        """Validate file exists."""
        if not UserFile.objects.filter(pk=value).exists():
            raise serializers.ValidationError("File not found")
        return value
    
    def validate_shared_with_id(self, value):
        """Validate user exists."""
        if value:
            from apps.authentication.models import User
            if not User.objects.filter(pk=value).exists():
                raise serializers.ValidationError("User not found")
        return value
    
    def validate(self, data):
        """Validate share settings."""
        if data.get('generate_public_link') and data.get('shared_with_id'):
            raise serializers.ValidationError("Cannot create public link and share with specific user")
        
        if not data.get('generate_public_link') and not data.get('shared_with_id'):
            raise serializers.ValidationError("Must either generate public link or specify user to share with")
        
        return data
