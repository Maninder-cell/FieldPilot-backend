"""
Tenant Admin

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import Tenant, TenantMember, TenantSettings, TechnicianWageRate


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'trial_ends_at', 'onboarding_completed', 'created_at']
    list_filter = ['is_active', 'onboarding_completed', 'industry', 'company_size']
    search_fields = ['name', 'slug', 'company_email']
    readonly_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'company_email', 'company_phone', 'website')
        }),
        ('Company Details', {
            'fields': ('industry', 'company_size', 'address', 'city', 'state', 'zip_code', 'country')
        }),
        ('Status', {
            'fields': ('is_active', 'trial_ends_at', 'onboarding_completed', 'onboarding_step')
        }),
        ('Settings', {
            'fields': ('settings',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(TenantMember)
class TenantMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active']
    search_fields = ['user__email', 'tenant__name']
    readonly_fields = ['id', 'joined_at']


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'timezone', 'language', 'email_notifications', 'created_at']
    list_filter = ['timezone', 'language', 'email_notifications']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TechnicianWageRate)
class TechnicianWageRateAdmin(admin.ModelAdmin):
    list_display = ['technician', 'normal_hourly_rate', 'overtime_hourly_rate', 'effective_from', 'effective_to', 'is_active']
    list_filter = ['is_active', 'effective_from']
    search_fields = ['technician__email', 'technician__first_name', 'technician__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'effective_from'
    
    fieldsets = (
        ('Technician', {
            'fields': ('technician',)
        }),
        ('Rates', {
            'fields': ('normal_hourly_rate', 'overtime_hourly_rate')
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to', 'is_active')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Set created_by to current user if not set."""
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)