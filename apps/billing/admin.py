"""
Billing Admin

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from .models import SubscriptionPlan, Subscription, Invoice, Payment, UsageRecord


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'price_monthly', 'price_yearly', 
        'max_users', 'max_equipment', 'is_active', 'sort_order'
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'sort_order')
        }),
        ('Pricing', {
            'fields': ('price_monthly', 'price_yearly')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_yearly')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_equipment', 'max_storage_gb', 'max_api_calls_per_month')
        }),
        ('Features', {
            'fields': ('features',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'plan', 'status', 'billing_cycle', 
        'current_period_end', 'cancel_at_period_end', 'created_at'
    ]
    list_filter = ['status', 'billing_cycle', 'cancel_at_period_end', 'plan']
    search_fields = ['tenant__name', 'stripe_subscription_id', 'stripe_customer_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'plan', 'status', 'billing_cycle')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Trial', {
            'fields': ('trial_start', 'trial_end')
        }),
        ('Cancellation', {
            'fields': ('cancel_at_period_end', 'canceled_at', 'cancellation_reason')
        }),
        ('Usage Tracking', {
            'fields': (
                'current_users_count', 'current_equipment_count', 
                'current_storage_gb', 'current_api_calls_this_month'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'tenant', 'total', 'currency', 
        'status', 'issue_date', 'due_date', 'paid_at'
    ]
    list_filter = ['status', 'currency', 'issue_date']
    search_fields = ['invoice_number', 'tenant__name', 'stripe_invoice_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'issue_date'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'amount', 'currency', 'payment_method', 
        'status', 'processed_at', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'currency']
    search_fields = ['tenant__name', 'stripe_payment_intent_id', 'stripe_charge_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = [
        'tenant', 'metric_name', 'value', 'unit', 'recorded_at'
    ]
    list_filter = ['metric_name', 'unit', 'recorded_at']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'recorded_at'