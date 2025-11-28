"""
Billing Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import SubscriptionPlan, Subscription


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


class SubscriptionSerializer(serializers.Serializer):
    """
    Serializer for subscriptions - fetches billing data from Stripe dynamically.
    """
    id = serializers.UUIDField(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    
    # Stripe data (fetched dynamically from Stripe subscription)
    billing_cycle = serializers.SerializerMethodField()
    current_period_start = serializers.SerializerMethodField()
    current_period_end = serializers.SerializerMethodField()
    cancel_at_period_end = serializers.SerializerMethodField()
    canceled_at = serializers.SerializerMethodField()
    trial_start = serializers.SerializerMethodField()
    trial_end = serializers.SerializerMethodField()
    
    # Computed fields
    is_active = serializers.SerializerMethodField()
    is_trial = serializers.SerializerMethodField()
    days_until_renewal = serializers.SerializerMethodField()
    
    # Local usage data
    current_users_count = serializers.IntegerField(read_only=True)
    current_equipment_count = serializers.IntegerField(read_only=True)
    current_storage_gb = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    usage_limits_exceeded = serializers.SerializerMethodField()
    
    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    
    def _get_stripe_subscription(self, obj):
        """Get Stripe subscription from context or fetch it."""
        # Check if Stripe subscription is in context (passed from view)
        stripe_sub = self.context.get('stripe_subscription')
        if stripe_sub:
            return stripe_sub
        
        # Otherwise fetch from Stripe
        try:
            from .stripe_service import StripeService
            return StripeService.get_subscription(obj.stripe_subscription_id)
        except Exception:
            return None
    
    def get_billing_cycle(self, obj):
        """Get billing cycle from model (stored locally)."""
        return obj.billing_cycle if hasattr(obj, 'billing_cycle') else None
    
    def get_current_period_start(self, obj):
        """Get current period start from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            from datetime import datetime
            from django.utils import timezone
            
            # Try current_period_start first
            current_period_start = getattr(stripe_sub, 'current_period_start', None)
            if current_period_start:
                return datetime.fromtimestamp(current_period_start, tz=timezone.utc)
            
            # Fall back to billing_cycle_anchor (for subscriptions after trial)
            billing_cycle_anchor = getattr(stripe_sub, 'billing_cycle_anchor', None)
            if billing_cycle_anchor:
                return datetime.fromtimestamp(billing_cycle_anchor, tz=timezone.utc)
            
            # Fall back to trial_end (if trial just ended)
            trial_end = getattr(stripe_sub, 'trial_end', None)
            if trial_end:
                return datetime.fromtimestamp(trial_end, tz=timezone.utc)
        return None
    
    def get_current_period_end(self, obj):
        """Get current period end from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            from datetime import datetime, timedelta
            from django.utils import timezone
            
            # Try current_period_end first
            current_period_end = getattr(stripe_sub, 'current_period_end', None)
            if current_period_end:
                return datetime.fromtimestamp(current_period_end, tz=timezone.utc)
            
            # Calculate from billing_cycle_anchor + billing cycle
            billing_cycle_anchor = getattr(stripe_sub, 'billing_cycle_anchor', None)
            if billing_cycle_anchor:
                start = datetime.fromtimestamp(billing_cycle_anchor, tz=timezone.utc)
                # Add 30 days for monthly, 365 for yearly (default to monthly)
                if obj.billing_cycle == 'yearly':
                    return start + timedelta(days=365)
                else:
                    return start + timedelta(days=30)
        return None
    
    def get_cancel_at_period_end(self, obj):
        """Get cancel at period end from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            return getattr(stripe_sub, 'cancel_at_period_end', False)
        return False
    
    def get_canceled_at(self, obj):
        """Get canceled at timestamp from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            canceled_at = getattr(stripe_sub, 'canceled_at', None)
            if canceled_at:
                from datetime import datetime
                from django.utils import timezone
                return datetime.fromtimestamp(canceled_at, tz=timezone.utc)
        return None
    
    def get_trial_start(self, obj):
        """Get trial start from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            trial_start = getattr(stripe_sub, 'trial_start', None)
            if trial_start:
                from datetime import datetime
                from django.utils import timezone
                return datetime.fromtimestamp(trial_start, tz=timezone.utc)
        return None
    
    def get_trial_end(self, obj):
        """Get trial end from Stripe subscription."""
        stripe_sub = self._get_stripe_subscription(obj)
        if stripe_sub:
            trial_end = getattr(stripe_sub, 'trial_end', None)
            if trial_end:
                from datetime import datetime
                from django.utils import timezone
                return datetime.fromtimestamp(trial_end, tz=timezone.utc)
        return None
    
    def get_is_active(self, obj):
        """Check if subscription is active."""
        return obj.is_active
    
    def get_is_trial(self, obj):
        """Check if subscription is in trial."""
        return obj.is_trial
    
    def get_days_until_renewal(self, obj):
        """Calculate days until next renewal."""
        from django.utils import timezone
        
        # Get current period end from Stripe
        current_period_end = self.get_current_period_end(obj)
        if current_period_end:
            delta = current_period_end - timezone.now()
            return max(0, delta.days)
        
        # Fallback to trial end if in trial
        trial_end = self.get_trial_end(obj)
        if trial_end:
            delta = trial_end - timezone.now()
            return max(0, delta.days)
        
        return 0
    
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


class StripeInvoiceSerializer(serializers.Serializer):
    """
    Serializer for Stripe invoices.
    """
    id = serializers.CharField()  # Stripe invoice ID
    number = serializers.CharField()
    amount_due = serializers.IntegerField()  # In cents
    amount_paid = serializers.IntegerField()  # In cents
    currency = serializers.CharField()
    status = serializers.CharField()
    created = serializers.IntegerField()  # Unix timestamp
    due_date = serializers.IntegerField(allow_null=True)  # Unix timestamp
    paid_at = serializers.IntegerField(allow_null=True)  # Unix timestamp (status_transitions.paid_at)
    invoice_pdf = serializers.URLField(allow_null=True)
    period_start = serializers.IntegerField(allow_null=True)  # Unix timestamp
    period_end = serializers.IntegerField(allow_null=True)  # Unix timestamp
    
    def to_representation(self, instance):
        """Convert Stripe invoice object to dict with formatted values."""
        from datetime import datetime
        from django.utils import timezone
        
        # Helper to convert cents to dollars
        def cents_to_dollars(cents):
            return round(cents / 100, 2) if cents else 0
        
        # Helper to convert timestamp to ISO string
        def timestamp_to_iso(timestamp):
            if timestamp:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            return None
        
        return {
            'id': instance.id,
            'number': instance.number,
            'amount_due': cents_to_dollars(instance.amount_due),
            'amount_paid': cents_to_dollars(instance.amount_paid),
            'currency': instance.currency.upper(),
            'status': instance.status,
            'created': timestamp_to_iso(instance.created),
            'due_date': timestamp_to_iso(instance.due_date),
            'paid_at': timestamp_to_iso(instance.status_transitions.paid_at) if instance.status_transitions else None,
            'invoice_pdf': instance.invoice_pdf,
            'period_start': timestamp_to_iso(instance.period_start),
            'period_end': timestamp_to_iso(instance.period_end),
        }


class StripeChargeSerializer(serializers.Serializer):
    """
    Serializer for Stripe charges (payments).
    """
    id = serializers.CharField()  # Stripe charge ID
    amount = serializers.IntegerField()  # In cents
    currency = serializers.CharField()
    status = serializers.CharField()
    payment_method_details = serializers.DictField()
    failure_code = serializers.CharField(allow_null=True)
    failure_message = serializers.CharField(allow_null=True)
    created = serializers.IntegerField()  # Unix timestamp
    receipt_url = serializers.URLField(allow_null=True)
    
    def to_representation(self, instance):
        """Convert Stripe charge object to dict with formatted values."""
        from datetime import datetime
        from django.utils import timezone
        
        # Helper to convert cents to dollars
        def cents_to_dollars(cents):
            return round(cents / 100, 2) if cents else 0
        
        # Helper to convert timestamp to ISO string
        def timestamp_to_iso(timestamp):
            if timestamp:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            return None
        
        # Format payment method details
        payment_method_details = {}
        if instance.payment_method_details:
            if instance.payment_method_details.card:
                payment_method_details = {
                    'type': 'card',
                    'brand': instance.payment_method_details.card.brand.capitalize(),
                    'last4': instance.payment_method_details.card.last4,
                    'exp_month': instance.payment_method_details.card.exp_month,
                    'exp_year': instance.payment_method_details.card.exp_year,
                }
        
        return {
            'id': instance.id,
            'amount': cents_to_dollars(instance.amount),
            'currency': instance.currency.upper(),
            'status': instance.status,
            'payment_method_details': payment_method_details,
            'failure_code': instance.failure_code,
            'failure_message': instance.failure_message,
            'created': timestamp_to_iso(instance.created),
            'receipt_url': instance.receipt_url,
        }


class PaymentMethodSerializer(serializers.Serializer):
    """
    Serializer for payment method operations.
    """
    payment_method_id = serializers.CharField()
    set_as_default = serializers.BooleanField(default=False)


class StripePaymentMethodSerializer(serializers.Serializer):
    """
    Serializer for Stripe payment methods.
    """
    id = serializers.CharField()
    type = serializers.CharField()
    card = serializers.DictField()
    is_default = serializers.BooleanField()
    
    def to_representation(self, instance):
        """Convert Stripe payment method object to dict."""
        # instance is a Stripe PaymentMethod object
        card_data = {}
        if instance.card:
            card_data = {
                'brand': instance.card.brand,
                'last4': instance.card.last4,
                'exp_month': instance.card.exp_month,
                'exp_year': instance.card.exp_year,
            }
        
        # Check if this is the default payment method
        default_payment_method_id = self.context.get('default_payment_method_id')
        is_default = instance.id == default_payment_method_id
        
        return {
            'id': instance.id,
            'type': instance.type,
            'card': card_data,
            'is_default': is_default,
        }


class BillingOverviewSerializer(serializers.Serializer):
    """
    Serializer for billing overview/dashboard - fetches data from Stripe.
    """
    subscription = SubscriptionSerializer(allow_null=True)
    current_invoice = StripeInvoiceSerializer(allow_null=True)
    recent_payments = StripeChargeSerializer(many=True)
    usage_summary = serializers.DictField()
    
    def to_representation(self, instance):
        """Custom representation for billing overview using Stripe data."""
        tenant = instance
        
        # Get subscription from context
        subscription = self.context.get('subscription')
        stripe_subscription = self.context.get('stripe_subscription')
        current_invoice = self.context.get('current_invoice')
        recent_charges = self.context.get('recent_charges', [])
        
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
            'subscription': SubscriptionSerializer(subscription, context={'stripe_subscription': stripe_subscription}).data if subscription else None,
            'current_invoice': StripeInvoiceSerializer(current_invoice).data if current_invoice else None,
            'recent_payments': StripeChargeSerializer(recent_charges, many=True).data,
            'usage_summary': usage_summary
        }