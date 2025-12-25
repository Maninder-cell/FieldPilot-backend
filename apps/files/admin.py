"""
Files Admin

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import UserFile, FileShare


@admin.register(UserFile)
class UserFileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'uploaded_by', 'file_size_mb', 'file_type', 'is_image', 'is_attached', 'created_at']
    list_filter = ['is_image', 'is_public', 'file_type', 'created_at']
    search_fields = ['filename', 'title', 'description', 'uploaded_by__email']
    readonly_fields = ['id', 'file_size', 'file_type', 'is_image', 'created_at', 'updated_at']
    raw_id_fields = ['uploaded_by', 'service_request']
    
    fieldsets = (
        ('File Information', {
            'fields': ('file', 'filename', 'file_size', 'file_type', 'is_image')
        }),
        ('Metadata', {
            'fields': ('title', 'description', 'tags', 'is_public')
        }),
        ('Ownership', {
            'fields': ('uploaded_by',)
        }),
        ('Attachments', {
            'fields': ('service_request',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )


@admin.register(FileShare)
class FileShareAdmin(admin.ModelAdmin):
    list_display = ['file', 'shared_by', 'shared_with', 'is_public', 'can_download', 'access_count', 'created_at']
    list_filter = ['can_download', 'can_edit', 'created_at']
    search_fields = ['file__filename', 'shared_by__email', 'shared_with__email', 'share_token']
    readonly_fields = ['id', 'share_token', 'access_count', 'last_accessed_at', 'created_at']
    raw_id_fields = ['file', 'shared_by', 'shared_with']
    
    fieldsets = (
        ('Share Information', {
            'fields': ('file', 'shared_by', 'shared_with')
        }),
        ('Permissions', {
            'fields': ('can_download', 'can_edit', 'expires_at')
        }),
        ('Public Link', {
            'fields': ('share_token',)
        }),
        ('Tracking', {
            'fields': ('access_count', 'last_accessed_at', 'created_at')
        }),
    )
