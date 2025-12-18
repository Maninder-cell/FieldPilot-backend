"""
Tasks Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    Task, TechnicianTeam, TaskAssignment, TimeLog,
    TaskComment, TaskAttachment, TaskHistory, MaterialLog
)
from apps.authentication.serializers import UserSerializer
from apps.equipment.serializers import EquipmentSerializer


# Task Serializers

class TaskAssignmentSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskAssignment with assignee details.
    """
    assignee = UserSerializer(read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    assignee_name = serializers.ReadOnlyField()
    
    class Meta:
        model = TaskAssignment
        fields = [
            'id', 'task', 'assignee', 'team', 'team_name', 'assignee_name',
            'work_status', 'assigned_by', 'assigned_at'
        ]
        read_only_fields = ['id', 'assigned_by', 'assigned_at']


class TaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for task list views.
    """
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_number = serializers.CharField(source='equipment.equipment_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    assignment_count = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'task_number', 'title', 'status', 'priority',
            'equipment_name', 'equipment_number', 'created_by_name',
            'assignment_count', 'is_active', 'scheduled_start',
            'is_scheduled', 'created_at', 'updated_at'
        ]
    
    def get_assignment_count(self, obj):
        return obj.assignments.count()


class TaskSerializer(serializers.ModelSerializer):
    """
    Full task serializer with nested relationships.
    """
    equipment = EquipmentSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    assignments = TaskAssignmentSerializer(many=True, read_only=True)
    
    # Counts
    comments_count = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()
    
    # Computed fields
    is_active = serializers.ReadOnlyField()
    is_visible_to_technicians = serializers.ReadOnlyField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'task_number', 'title', 'description',
            'equipment', 'status', 'priority',
            'scheduled_start', 'scheduled_end', 'is_scheduled',
            'materials_needed', 'materials_received',
            'notes', 'custom_fields',
            'assignments', 'comments_count', 'attachments_count',
            'is_active', 'is_visible_to_technicians',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'task_number', 'is_scheduled',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_comments_count(self, obj):
        return obj.comments.count()
    
    def get_attachments_count(self, obj):
        return obj.attachments.count()


class CreateTaskSerializer(serializers.Serializer):
    """
    Serializer for creating a new task.
    """
    equipment_id = serializers.UUIDField(required=True)
    title = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=True)
    priority = serializers.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        default='medium'
    )
    status = serializers.ChoiceField(
        choices=Task.STATUS_CHOICES,
        default='new',
        required=False
    )
    
    # Assignment
    assignee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    
    # Scheduling
    scheduled_start = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_end = serializers.DateTimeField(required=False, allow_null=True)
    
    # Materials
    materials_needed = serializers.ListField(required=False, allow_empty=True)
    
    # Additional
    notes = serializers.CharField(required=False, allow_blank=True)
    custom_fields = serializers.JSONField(required=False)
    
    def validate_equipment_id(self, value):
        """Validate equipment exists."""
        from apps.equipment.models import Equipment
        try:
            equipment = Equipment.objects.get(pk=value)
            self.equipment = equipment
            return value
        except Equipment.DoesNotExist:
            raise serializers.ValidationError("Equipment not found.")
    
    def validate(self, data):
        """Validate task data."""
        # Ensure at least one assignee or team
        assignee_ids = data.get('assignee_ids', [])
        team_ids = data.get('team_ids', [])
        
        if not assignee_ids and not team_ids:
            raise serializers.ValidationError(
                "At least one assignee or team is required."
            )
        
        # Validate scheduled dates
        scheduled_start = data.get('scheduled_start')
        scheduled_end = data.get('scheduled_end')
        
        if scheduled_start and scheduled_end:
            if scheduled_end <= scheduled_start:
                raise serializers.ValidationError({
                    'scheduled_end': 'Scheduled end must be after scheduled start.'
                })
        
        # Validate assignees are technicians
        if assignee_ids:
            from apps.authentication.models import User
            from apps.tenants.models import TenantMember
            from django.db import connection
            from django_tenants.utils import schema_context
            
            assignees = User.objects.filter(pk__in=assignee_ids)
            
            if assignees.count() != len(assignee_ids):
                raise serializers.ValidationError({
                    'assignee_ids': 'One or more assignees not found.'
                })
            
            # Check if all assignees are technicians in the current tenant
            tenant = getattr(connection, 'tenant', None)
            if tenant:
                with schema_context('public'):
                    for assignee in assignees:
                        membership = TenantMember.objects.filter(
                            tenant_id=tenant.id,
                            user=assignee,
                            is_active=True
                        ).first()
                        
                        if not membership or membership.role != 'technician':
                            raise serializers.ValidationError({
                                'assignee_ids': f'User {assignee.email} is not a technician in this tenant.'
                            })
            
            self.assignees = list(assignees)
        
        # Validate teams exist and are active
        if team_ids:
            teams = TechnicianTeam.objects.filter(pk__in=team_ids, is_active=True)
            
            if teams.count() != len(team_ids):
                raise serializers.ValidationError({
                    'team_ids': 'One or more teams not found or inactive.'
                })
            
            self.teams = list(teams)
        
        return data


class UpdateTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for updating task information.
    """
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'status',
            'scheduled_start', 'scheduled_end',
            'materials_needed', 'materials_received',
            'notes', 'custom_fields'
        ]
    
    def validate(self, data):
        """Validate update data."""
        # Validate scheduled dates if both provided
        scheduled_start = data.get('scheduled_start', self.instance.scheduled_start)
        scheduled_end = data.get('scheduled_end', self.instance.scheduled_end)
        
        if scheduled_start and scheduled_end:
            if scheduled_end <= scheduled_start:
                raise serializers.ValidationError({
                    'scheduled_end': 'Scheduled end must be after scheduled start.'
                })
        
        # Validate status transition
        if 'status' in data and data['status'] != self.instance.status:
            from .utils import TaskStatusValidator
            try:
                TaskStatusValidator.validate_status_transition(
                    self.instance,
                    data['status']
                )
            except DjangoValidationError as e:
                raise serializers.ValidationError({'status': str(e)})
        
        return data


class AssignTaskSerializer(serializers.Serializer):
    """
    Serializer for assigning task to technicians or teams.
    """
    assignee_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    
    def validate(self, data):
        """Validate assignment data."""
        assignee_ids = data.get('assignee_ids', [])
        team_ids = data.get('team_ids', [])
        
        if not assignee_ids and not team_ids:
            raise serializers.ValidationError(
                "At least one assignee or team is required."
            )
        
        # Validate assignees
        if assignee_ids:
            from apps.authentication.models import User
            from apps.tenants.models import TenantMember
            from django.db import connection
            from django_tenants.utils import schema_context
            
            assignees = User.objects.filter(pk__in=assignee_ids)
            
            if assignees.count() != len(assignee_ids):
                raise serializers.ValidationError({
                    'assignee_ids': 'One or more assignees not found.'
                })
            
            # Check if all assignees are technicians in the current tenant
            tenant = getattr(connection, 'tenant', None)
            if tenant:
                with schema_context('public'):
                    for assignee in assignees:
                        membership = TenantMember.objects.filter(
                            tenant_id=tenant.id,
                            user=assignee,
                            is_active=True,
                            role='technician'
                        ).first()
                        
                        if not membership:
                            raise serializers.ValidationError({
                                'assignee_ids': f'User {assignee.email} is not a technician in this tenant.'
                            })
            
            self.assignees = list(assignees)
        
        # Validate teams
        if team_ids:
            teams = TechnicianTeam.objects.filter(pk__in=team_ids, is_active=True)
            
            if teams.count() != len(team_ids):
                raise serializers.ValidationError({
                    'team_ids': 'One or more teams not found or inactive.'
                })
            
            self.teams = list(teams)
        
        return data


class UpdateTaskStatusSerializer(serializers.Serializer):
    """
    Serializer for updating task administrative status.
    """
    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES, required=True)
    
    def validate_status(self, value):
        """Validate status transition."""
        task = self.context.get('task')
        if not task:
            return value
        
        from .utils import TaskStatusValidator
        try:
            TaskStatusValidator.validate_status_transition(task, value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))
        
        return value


class UpdateWorkStatusSerializer(serializers.Serializer):
    """
    Serializer for updating work status by technician.
    """
    work_status = serializers.ChoiceField(
        choices=TaskAssignment.WORK_STATUS_CHOICES,
        required=True
    )
    
    def validate_work_status(self, value):
        """Validate work status transition."""
        assignment = self.context.get('assignment')
        if not assignment:
            return value
        
        from .utils import TaskStatusValidator
        try:
            TaskStatusValidator.validate_work_status_transition(assignment, value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))
        
        return value



# Team Management Serializers

class TechnicianTeamSerializer(serializers.ModelSerializer):
    """
    Serializer for TechnicianTeam with member details.
    """
    members = UserSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    member_count = serializers.ReadOnlyField()
    active_member_count = serializers.ReadOnlyField()
    
    class Meta:
        model = TechnicianTeam
        fields = [
            'id', 'name', 'description', 'members', 'is_active',
            'member_count', 'active_member_count',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'updated_by', 'created_at', 'updated_at']


class TechnicianTeamListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for team list views.
    """
    member_count = serializers.ReadOnlyField()
    active_member_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = TechnicianTeam
        fields = [
            'id', 'name', 'description', 'is_active',
            'member_count', 'active_member_count',
            'created_by_name', 'created_at'
        ]


class CreateTeamSerializer(serializers.Serializer):
    """
    Serializer for creating a new team.
    """
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    is_active = serializers.BooleanField(default=True)
    
    def validate_name(self, value):
        """Validate team name is unique."""
        if TechnicianTeam.objects.filter(name=value).exists():
            raise serializers.ValidationError("A team with this name already exists.")
        return value
    
    def validate_member_ids(self, value):
        """Validate members are technicians."""
        if not value:
            return value
        
        from apps.authentication.models import User
        from apps.tenants.models import TenantMember
        from django.db import connection
        from django_tenants.utils import schema_context
        
        members = User.objects.filter(pk__in=value, is_active=True)
        
        if members.count() != len(value):
            raise serializers.ValidationError(
                "One or more members not found or not active."
            )
        
        # Check if all members are technicians in the current tenant
        tenant = getattr(connection, 'tenant', None)
        if tenant:
            with schema_context('public'):
                for member in members:
                    membership = TenantMember.objects.filter(
                        tenant_id=tenant.id,
                        user=member,
                        is_active=True,
                        role='technician'
                    ).first()
                    
                    if not membership:
                        raise serializers.ValidationError(
                            f"User {member.email} is not a technician in this tenant."
                        )
        
        self.members = list(members)
        return value
    
    def validate(self, data):
        """Validate team data."""
        return data


class UpdateTeamSerializer(serializers.ModelSerializer):
    """
    Serializer for updating team information.
    """
    class Meta:
        model = TechnicianTeam
        fields = ['name', 'description', 'is_active']
    
    def validate_name(self, value):
        """Validate team name is unique."""
        existing = TechnicianTeam.objects.filter(name=value).exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("A team with this name already exists.")
        return value


class AddTeamMembersSerializer(serializers.Serializer):
    """
    Serializer for adding members to a team.
    """
    member_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        allow_empty=False
    )
    
    def validate_member_ids(self, value):
        """Validate members are technicians."""
        from apps.authentication.models import User
        from apps.tenants.models import TenantMember
        from django.db import connection
        from django_tenants.utils import schema_context
        
        members = User.objects.filter(pk__in=value, is_active=True)
        
        if members.count() != len(value):
            raise serializers.ValidationError(
                "One or more members not found or not active."
            )
        
        # Check if all members are technicians in the current tenant
        tenant = getattr(connection, 'tenant', None)
        if tenant:
            with schema_context('public'):
                for member in members:
                    membership = TenantMember.objects.filter(
                        tenant_id=tenant.id,
                        user=member,
                        is_active=True,
                        role='technician'
                    ).first()
                    
                    if not membership:
                        raise serializers.ValidationError(
                            f"User {member.email} is not a technician in this tenant."
                        )
        
        self.members = list(members)
        return value


class TechnicianListSerializer(serializers.Serializer):
    """
    Serializer for listing technicians for team selection.
    """
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.URLField(read_only=True)
    employee_id = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    
    def get_employee_id(self, obj):
        """Get employee_id from TenantMember."""
        tenant_member = getattr(obj, 'tenant_member', None)
        return tenant_member.employee_id if tenant_member else ''
    
    def get_department(self, obj):
        """Get department from TenantMember."""
        tenant_member = getattr(obj, 'tenant_member', None)
        return tenant_member.department if tenant_member else ''
    
    def get_job_title(self, obj):
        """Get job_title from TenantMember."""
        tenant_member = getattr(obj, 'tenant_member', None)
        return tenant_member.job_title if tenant_member else ''
    
    def get_phone(self, obj):
        """Get phone from TenantMember."""
        tenant_member = getattr(obj, 'tenant_member', None)
        return tenant_member.phone if tenant_member else ''



# Time Tracking Serializers

class TimeLogSerializer(serializers.ModelSerializer):
    """
    Serializer for TimeLog with technician details and calculated hours.
    """
    technician = UserSerializer(read_only=True)
    task_number = serializers.CharField(source='task.task_number', read_only=True)
    is_on_site = serializers.ReadOnlyField()
    is_traveling = serializers.ReadOnlyField()
    is_on_lunch = serializers.ReadOnlyField()
    can_start_lunch = serializers.ReadOnlyField()
    can_end_lunch = serializers.ReadOnlyField()
    
    class Meta:
        model = TimeLog
        fields = [
            'id', 'task', 'task_number', 'technician',
            'travel_started_at', 'arrived_at', 'departed_at',
            'lunch_started_at', 'lunch_ended_at',
            'equipment_status_at_departure',
            'total_work_hours', 'normal_hours', 'overtime_hours',
            'is_on_site', 'is_traveling', 'is_on_lunch',
            'can_start_lunch', 'can_end_lunch',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_work_hours', 'normal_hours', 'overtime_hours',
            'created_at', 'updated_at'
        ]


class TravelLogSerializer(serializers.Serializer):
    """
    Serializer for logging travel start.
    """
    def validate(self, data):
        """Validate technician can travel."""
        task = self.context.get('task')
        technician = self.context.get('technician')
        
        if not task or not technician:
            raise serializers.ValidationError("Task and technician required.")
        
        # Check if technician can travel
        from .utils import SiteConflictValidator
        try:
            SiteConflictValidator.validate_travel(technician, task)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))
        
        return data


class ArrivalLogSerializer(serializers.Serializer):
    """
    Serializer for logging arrival at site.
    """
    def validate(self, data):
        """Validate arrival."""
        time_log = self.context.get('time_log')
        
        if not time_log:
            raise serializers.ValidationError("Time log not found.")
        
        if time_log.arrived_at:
            raise serializers.ValidationError("Already arrived at site.")
        
        if time_log.departed_at:
            raise serializers.ValidationError("Cannot arrive after departure.")
        
        return data


class DepartureLogSerializer(serializers.Serializer):
    """
    Serializer for logging departure from site.
    """
    equipment_status = serializers.ChoiceField(
        choices=TimeLog.EQUIPMENT_STATUS_CHOICES,
        required=True
    )
    
    def validate(self, data):
        """Validate departure."""
        time_log = self.context.get('time_log')
        
        if not time_log:
            raise serializers.ValidationError("Time log not found.")
        
        if not time_log.arrived_at:
            raise serializers.ValidationError("Must arrive at site before departing.")
        
        if time_log.departed_at:
            raise serializers.ValidationError("Already departed from site.")
        
        # Check if lunch is still active
        if time_log.is_on_lunch:
            raise serializers.ValidationError("Cannot depart while on lunch break.")
        
        return data


class LunchStartSerializer(serializers.Serializer):
    """
    Serializer for logging lunch start.
    """
    def validate(self, data):
        """Validate lunch start."""
        time_log = self.context.get('time_log')
        
        if not time_log:
            raise serializers.ValidationError("Time log not found.")
        
        if not time_log.can_start_lunch:
            if not time_log.is_on_site:
                raise serializers.ValidationError("Must be on site to start lunch.")
            if time_log.is_on_lunch:
                raise serializers.ValidationError("Lunch already started.")
        
        return data


class LunchEndSerializer(serializers.Serializer):
    """
    Serializer for logging lunch end.
    """
    def validate(self, data):
        """Validate lunch end."""
        time_log = self.context.get('time_log')
        
        if not time_log:
            raise serializers.ValidationError("Time log not found.")
        
        if not time_log.can_end_lunch:
            raise serializers.ValidationError("No active lunch break to end.")
        
        return data



# Comment Serializers

class TaskCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskComment with author details.
    """
    author = UserSerializer(read_only=True)
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    author_role = serializers.CharField(source='author.role', read_only=True)
    task_number = serializers.CharField(source='task.task_number', read_only=True)
    
    class Meta:
        model = TaskComment
        fields = [
            'id', 'task', 'task_number', 'author', 'author_name', 'author_role',
            'comment', 'is_system_generated',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_system_generated', 'created_at', 'updated_at']


class CreateCommentSerializer(serializers.Serializer):
    """
    Serializer for creating a comment.
    """
    comment = serializers.CharField(required=True, allow_blank=False)
    
    def validate_comment(self, value):
        """Validate comment is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()


class UpdateCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for updating a comment.
    """
    class Meta:
        model = TaskComment
        fields = ['comment']
    
    def validate_comment(self, value):
        """Validate comment is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()
    
    def validate(self, data):
        """Validate user can update comment."""
        # System-generated comments cannot be edited
        if self.instance.is_system_generated:
            raise serializers.ValidationError("System-generated comments cannot be edited.")
        
        return data


# Attachment Serializers

class TaskAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for TaskAttachment with metadata.
    """
    uploaded_by = UserSerializer(read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    task_number = serializers.CharField(source='task.task_number', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskAttachment
        fields = [
            'id', 'task', 'task_number', 'uploaded_by', 'uploaded_by_name',
            'file', 'file_url', 'filename', 'file_size', 'file_size_mb',
            'file_type', 'is_image', 'created_at'
        ]
        read_only_fields = ['id', 'file_size', 'file_type', 'is_image', 'created_at']
    
    def get_file_url(self, obj):
        """Get file URL."""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_file_size_mb(self, obj):
        """Get file size in MB."""
        return round(obj.file_size / (1024 * 1024), 2)


class UploadAttachmentSerializer(serializers.Serializer):
    """
    Serializer for uploading file attachments.
    """
    file = serializers.FileField(required=True)
    
    def validate_file(self, value):
        """Validate file upload."""
        # Validate file size (10MB max)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"File size must not exceed {MAX_FILE_SIZE / (1024 * 1024)}MB."
            )
        
        # Validate file type
        ALLOWED_TYPES = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain',
            'text/csv',
        ]
        
        content_type = value.content_type
        if content_type not in ALLOWED_TYPES:
            raise serializers.ValidationError(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: images, PDF, Word, Excel, text files."
            )
        
        return value



# Material Tracking Serializers

class MaterialLogSerializer(serializers.ModelSerializer):
    """
    Serializer for MaterialLog.
    """
    logged_by = UserSerializer(read_only=True)
    logged_by_name = serializers.CharField(source='logged_by.full_name', read_only=True)
    task_number = serializers.CharField(source='task.task_number', read_only=True)
    
    class Meta:
        model = MaterialLog
        fields = [
            'id', 'task', 'task_number', 'log_type',
            'material_name', 'quantity', 'unit', 'notes',
            'logged_by', 'logged_by_name', 'logged_at'
        ]
        read_only_fields = ['id', 'logged_at']


class LogMaterialSerializer(serializers.Serializer):
    """
    Serializer for logging materials needed or received.
    """
    log_type = serializers.ChoiceField(
        choices=MaterialLog.LOG_TYPE_CHOICES,
        required=True
    )
    material_name = serializers.CharField(max_length=255, required=True)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=0.01
    )
    unit = serializers.CharField(max_length=50, required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_material_name(self, value):
        """Validate material name is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Material name cannot be empty.")
        return value.strip()
    
    def validate_unit(self, value):
        """Validate unit is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Unit cannot be empty.")
        return value.strip()


# History Serializers

class TaskHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for TaskHistory (audit trail).
    """
    user = UserSerializer(read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    task_number = serializers.CharField(source='task.task_number', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = TaskHistory
        fields = [
            'id', 'task', 'task_number', 'user', 'user_name',
            'action', 'action_display', 'field_name',
            'old_value', 'new_value', 'details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
