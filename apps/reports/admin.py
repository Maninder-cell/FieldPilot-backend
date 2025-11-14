"""
Reports Admin

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import ReportAuditLog, ReportSchedule


@admin.register(ReportAuditLog)
class ReportAuditLogAdmin(admin.ModelAdmin):
    list_display = ['report_type', 'user', 'format', 'status', 'generated_at', 'execution_time']
    list_filter = ['report_type', 'format', 'status', 'generated_at']
    search_fields = ['report_type', 'report_name', 'user__email', 'user__full_name']
    readonly_fields = ['generated_at']
    date_hierarchy = 'generated_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'frequency', 'is_active', 'last_run', 'next_run']
    list_filter = ['report_type', 'frequency', 'is_active']
    search_fields = ['name', 'report_type']
    readonly_fields = ['created_at', 'updated_at', 'last_run']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'report_type', 'filters', 'format')
        }),
        ('Schedule Configuration', {
            'fields': ('frequency', 'day_of_week', 'day_of_month', 'time_of_day')
        }),
        ('Recipients', {
            'fields': ('recipients',)
        }),
        ('Status', {
            'fields': ('is_active', 'last_run', 'next_run')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
