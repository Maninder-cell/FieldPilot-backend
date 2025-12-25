"""
Tasks Admin Configuration

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import (
    Task, TaskNumberSequence, TechnicianTeam, TaskAssignment,
    TimeLog, TaskComment, TaskAttachment, TaskHistory, MaterialLog
)


@admin.register(TaskNumberSequence)
class TaskNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ['id', 'last_number', 'created_at', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['task_number', 'title', 'equipment', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'is_scheduled', 'created_at']
    search_fields = ['task_number', 'title', 'description']
    readonly_fields = ['task_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(TechnicianTeam)
class TechnicianTeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'member_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['members']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ['task', 'assignee', 'team', 'work_status', 'assigned_at']
    list_filter = ['work_status', 'assigned_at']
    search_fields = ['task__task_number', 'assignee__email']
    readonly_fields = ['assigned_at', 'created_at', 'updated_at']


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ['task', 'technician', 'travel_started_at', 'arrived_at', 'departed_at', 'total_work_hours']
    list_filter = ['created_at']
    search_fields = ['task__task_number', 'technician__email']
    readonly_fields = ['total_work_hours', 'normal_hours', 'overtime_hours', 'created_at', 'updated_at']


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'author', 'is_system_generated', 'created_at']
    list_filter = ['is_system_generated', 'created_at']
    search_fields = ['task__task_number', 'author__email', 'comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ['task', 'filename', 'file_type', 'file_size', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['task__task_number', 'user_file__filename']
    readonly_fields = ['created_at']
    raw_id_fields = ['task', 'user_file']


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ['task', 'action', 'user', 'field_name', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['task__task_number', 'user__email', 'field_name']
    readonly_fields = ['created_at']


@admin.register(MaterialLog)
class MaterialLogAdmin(admin.ModelAdmin):
    list_display = ['task', 'log_type', 'material_name', 'quantity', 'unit', 'logged_by', 'logged_at']
    list_filter = ['log_type', 'logged_at']
    search_fields = ['task__task_number', 'material_name', 'logged_by__email']
    readonly_fields = ['logged_at']
