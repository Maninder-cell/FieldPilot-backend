"""
Tenant Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import Tenant, TenantMember, TenantSettings
from apps.authentication.serializers import UserSerializer


class TenantSerializer(serializers.ModelSerializer):
    """
    Serializer for Tenant model.
    """
    is_trial_active = serializers.ReadOnlyField()
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'company_email', 'company_phone', 'website',
            'company_size', 'industry', 'address', 'city', 'state', 'zip_code',
            'country', 'is_active', 'trial_ends_at', 'is_trial_active',
            'onboarding_completed', 'onboarding_step', 'member_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()


class CreateTenantSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new tenant/company.
    """
    class Meta:
        model = Tenant
        fields = [
            'name', 'company_email', 'company_phone', 'website',
            'company_size', 'industry', 'address', 'city', 'state',
            'zip_code', 'country'
        ]
    
    def validate_name(self, value):
        """Validate company name is unique."""
        if Tenant.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("A company with this name already exists.")
        return value


class UpdateTenantSerializer(serializers.ModelSerializer):
    """
    Serializer for updating tenant information.
    """
    class Meta:
        model = Tenant
        fields = [
            'name', 'company_email', 'company_phone', 'website',
            'company_size', 'industry', 'address', 'city', 'state',
            'zip_code', 'country'
        ]


class TenantMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant members.
    """
    user = UserSerializer(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = TenantMember
        fields = [
            'id', 'tenant', 'user', 'user_email', 'user_name', 'role', 
            'employee_id', 'department', 'job_title', 'phone',
            'is_active', 'joined_at'
        ]
        read_only_fields = ['id', 'joined_at', 'employee_id']


class InviteMemberSerializer(serializers.Serializer):
    """
    Serializer for inviting members to tenant.
    """
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=TenantMember.ROLE_CHOICES)
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)


class TenantSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant settings.
    """
    class Meta:
        model = TenantSettings
        fields = [
            'logo_url', 'primary_color', 'secondary_color',
            'features_enabled', 'email_notifications', 'sms_notifications',
            'push_notifications', 'timezone', 'language', 'date_format',
            'business_hours', 'custom_fields', 'integrations',
            'normal_working_hours_per_day', 'default_normal_hourly_rate',
            'default_overtime_hourly_rate', 'overtime_multiplier', 'currency'
        ]


class OnboardingStepSerializer(serializers.Serializer):
    """
    Serializer for onboarding step completion.
    """
    step = serializers.IntegerField(min_value=1, max_value=5)
    data = serializers.JSONField(required=False)


class TechnicianWageRateSerializer(serializers.ModelSerializer):
    """
    Serializer for technician wage rates.
    """
    technician_name = serializers.CharField(source='technician.full_name', read_only=True)
    technician_email = serializers.EmailField(source='technician.email', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        from .models import TechnicianWageRate
        model = TechnicianWageRate
        fields = [
            'id', 'technician', 'technician_name', 'technician_email',
            'normal_hourly_rate', 'overtime_hourly_rate',
            'effective_from', 'effective_to', 'is_active', 'notes',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_technician(self, value):
        """Validate that the user is a technician."""
        if value.role != 'technician':
            raise serializers.ValidationError("Wage rates can only be set for technicians.")
        return value


class CreateTechnicianWageRateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new technician wage rate.
    """
    class Meta:
        from .models import TechnicianWageRate
        model = TechnicianWageRate
        fields = [
            'technician', 'normal_hourly_rate', 'overtime_hourly_rate',
            'effective_from', 'effective_to', 'notes'
        ]
    
    def validate_technician(self, value):
        """Validate that the user is a technician."""
        if value.role != 'technician':
            raise serializers.ValidationError("Wage rates can only be set for technicians.")
        return value
    
    def validate(self, data):
        """Validate effective dates."""
        if data.get('effective_to') and data.get('effective_from'):
            if data['effective_to'] <= data['effective_from']:
                raise serializers.ValidationError({
                    'effective_to': 'Effective to date must be after effective from date.'
                })
        return data
