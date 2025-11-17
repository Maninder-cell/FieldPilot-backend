"""
Tenant Admin

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import Tenant, TenantMember, TenantSettings


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