"""
Billing Admin

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, Subscription


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
        'tenant', 'plan', 'status', 'stripe_link', 'created_at'
    ]
    list_filter = ['status', 'plan']
    search_fields = ['tenant__name', 'stripe_subscription_id', 'stripe_customer_id']
    readonly_fields = ['created_at', 'updated_at', 'stripe_dashboard_link']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'plan', 'status')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id', 'stripe_dashboard_link'),
            'description': 'Stripe is the source of truth for all billing data. View full details in Stripe dashboard.'
        }),
        ('Cancellation', {
            'fields': ('cancellation_reason',)
        }),
        ('Usage Tracking', {
            'fields': (
                'current_users_count', 'current_equipment_count', 
                'current_storage_gb', 'current_api_calls_this_month'
            ),
            'description': 'Local usage tracking for plan limit enforcement.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def stripe_link(self, obj):
        """Display clickable link to Stripe subscription."""
        if obj.stripe_subscription_id:
            url = f"https://dashboard.stripe.com/subscriptions/{obj.stripe_subscription_id}"
            return format_html('<a href="{}" target="_blank">View in Stripe</a>', url)
        return '-'
    stripe_link.short_description = 'Stripe'
    
    def stripe_dashboard_link(self, obj):
        """Display clickable links to Stripe dashboard."""
        links = []
        
        if obj.stripe_subscription_id:
            sub_url = f"https://dashboard.stripe.com/subscriptions/{obj.stripe_subscription_id}"
            links.append(format_html('<a href="{}" target="_blank">View Subscription</a>', sub_url))
        
        if obj.stripe_customer_id:
            cust_url = f"https://dashboard.stripe.com/customers/{obj.stripe_customer_id}"
            links.append(format_html('<a href="{}" target="_blank">View Customer</a>', cust_url))
        
        if links:
            return format_html(' | '.join(links))
        return '-'
    stripe_dashboard_link.short_description = 'Stripe Dashboard Links'


# Invoice, Payment, and UsageRecord models have been removed.
# All billing data is now managed through Stripe.
# View invoices and payments in the Stripe dashboard.