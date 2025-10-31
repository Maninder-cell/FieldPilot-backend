"""
Billing Serializers

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Invoice, Payment


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription plans.
    """
    yearly_discount_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'slug', 'description', 'price_monthly', 
            'price_yearly', 'yearly_discount_percentage', 'max_users', 
            'max_equipment', 'max_storage_gb', 'max_api_calls_per_month',
            'features', 'is_active'
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for subscriptions.
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    is_active = serializers.ReadOnlyField()
    is_trial = serializers.ReadOnlyField()
    days_until_renewal = serializers.ReadOnlyField()
    usage_limits_exceeded = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'billing_cycle', 'current_period_start',
            'current_period_end', 'cancel_at_period_end', 'canceled_at',
            'trial_start', 'trial_end', 'is_active', 'is_trial',
            'days_until_renewal', 'current_users_count', 'current_equipment_count',
            'current_storage_gb', 'usage_limits_exceeded', 'created_at'
        ]
    
    def get_usage_limits_exceeded(self, obj):
        """Get list of exceeded usage limits."""
        return obj.check_usage_limits()


class CreateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for creating a new subscription.
    """
    plan_slug = serializers.CharField()
    billing_cycle = serializers.ChoiceField(choices=['monthly', 'yearly'])
    payment_method_id = serializers.CharField(required=False)
    
    def validate_plan_slug(self, value):
        """Validate plan exists and is active."""
        try:
            plan = SubscriptionPlan.objects.get(slug=value, is_active=True)
            self.plan = plan
            return value
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive subscription plan.")


class UpdateSubscriptionSerializer(serializers.Serializer):
    """
    Serializer for updating subscription.
    """
    plan_slug = serializers.CharField(required=False)
    billing_cycle = serializers.ChoiceField(choices=['monthly', 'yearly'], required=False)
    cancel_at_period_end = serializers.BooleanField(required=False)
    
    def validate_plan_slug(self, value):
        """Validate plan exists and is active."""
        if value:
            try:
                plan = SubscriptionPlan.objects.get(slug=value, is_active=True)
                self.plan = plan
                return value
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError("Invalid or inactive subscription plan.")
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for invoices.
    """
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'subtotal', 'tax', 'total', 'currency',
            'status', 'issue_date', 'due_date', 'paid_at', 'invoice_pdf_url',
            'period_start', 'period_end', 'created_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for payments.
    """
    
    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'payment_method', 'status',
            'failure_code', 'failure_message', 'processed_at', 'created_at'
        ]


class PaymentMethodSerializer(serializers.Serializer):
    """
    Serializer for payment method operations.
    """
    payment_method_id = serializers.CharField()
    set_as_default = serializers.BooleanField(default=False)


class BillingOverviewSerializer(serializers.Serializer):
    """
    Serializer for billing overview/dashboard.
    """
    subscription = SubscriptionSerializer()
    current_invoice = InvoiceSerializer(allow_null=True)
    recent_payments = PaymentSerializer(many=True)
    usage_summary = serializers.DictField()
    
    def to_representation(self, instance):
        """Custom representation for billing overview."""
        tenant = instance
        
        try:
            subscription = tenant.subscription
        except Subscription.DoesNotExist:
            subscription = None
        
        # Get current invoice (latest unpaid)
        current_invoice = tenant.invoices.filter(
            status__in=['draft', 'open']
        ).first()
        
        # Get recent payments
        recent_payments = tenant.payments.filter(
            status='succeeded'
        ).order_by('-created_at')[:5]
        
        # Calculate usage summary
        usage_summary = {}
        if subscription:
            usage_summary = {
                'users': {
                    'current': subscription.current_users_count,
                    'limit': subscription.plan.max_users,
                    'percentage': (subscription.current_users_count / subscription.plan.max_users * 100) if subscription.plan.max_users else 0
                },
                'equipment': {
                    'current': subscription.current_equipment_count,
                    'limit': subscription.plan.max_equipment,
                    'percentage': (subscription.current_equipment_count / subscription.plan.max_equipment * 100) if subscription.plan.max_equipment else 0
                },
                'storage': {
                    'current': float(subscription.current_storage_gb),
                    'limit': subscription.plan.max_storage_gb,
                    'percentage': (float(subscription.current_storage_gb) / subscription.plan.max_storage_gb * 100) if subscription.plan.max_storage_gb else 0
                }
            }
        
        return {
            'subscription': SubscriptionSerializer(subscription).data if subscription else None,
            'current_invoice': InvoiceSerializer(current_invoice).data if current_invoice else None,
            'recent_payments': PaymentSerializer(recent_payments, many=True).data,
            'usage_summary': usage_summary
        }