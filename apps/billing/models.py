"""
Billing Models

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models
from django.utils import timezone
from decimal import Decimal


class SubscriptionPlan(models.Model):
    """
    Subscription plans available for tenants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    
    # Pricing
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stripe integration
    stripe_price_id_monthly = models.CharField(max_length=255, blank=True)
    stripe_price_id_yearly = models.CharField(max_length=255, blank=True)
    stripe_product_id = models.CharField(max_length=255, blank=True)
    
    # Limits
    max_users = models.IntegerField(null=True, blank=True)  # null = unlimited
    max_equipment = models.IntegerField(null=True, blank=True)
    max_storage_gb = models.IntegerField(null=True, blank=True)
    max_api_calls_per_month = models.IntegerField(null=True, blank=True)
    
    # Features (JSON field for flexibility)
    features = models.JSONField(default=dict)
    
    # Status
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_subscription_plans'
        ordering = ['sort_order', 'price_monthly']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
    
    def __str__(self):
        return self.name
    
    @property
    def yearly_discount_percentage(self):
        """Calculate yearly discount percentage."""
        if self.price_monthly and self.price_yearly:
            monthly_yearly = self.price_monthly * 12
            if monthly_yearly > 0:
                return round(((monthly_yearly - self.price_yearly) / monthly_yearly) * 100, 1)
        return 0


class Subscription(models.Model):
    """
    Tenant subscriptions - Stripe is the source of truth for billing data.
    This model stores only Stripe references and local usage tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'tenants.Tenant', 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # Stripe references (source of truth for billing)
    stripe_customer_id = models.CharField(max_length=255)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    
    # Local status cache (synced via webhooks)
    status = models.CharField(
        max_length=50,
        choices=[
            ('active', 'Active'),
            ('trialing', 'Trialing'),
            ('past_due', 'Past Due'),
            ('canceled', 'Canceled'),
            ('unpaid', 'Unpaid'),
            ('incomplete', 'Incomplete'),
            ('incomplete_expired', 'Incomplete Expired'),
        ],
        default='trialing'
    )
    
    # Billing cycle
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        default='monthly'
    )
    
    # Cancellation tracking
    cancellation_reason = models.TextField(blank=True)
    
    # Usage tracking (local only)
    current_users_count = models.IntegerField(default=0)
    current_equipment_count = models.IntegerField(default=0)
    current_storage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_api_calls_this_month = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_subscriptions'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        indexes = [
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['stripe_subscription_id']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name}"
    
    @property
    def is_active(self):
        """Check if subscription is active."""
        return self.status in ['active', 'trialing']
    
    @property
    def is_trial(self):
        """Check if subscription is in trial."""
        return self.status == 'trialing'
    
    def sync_from_stripe(self):
        """
        Fetch latest subscription data from Stripe and update local status.
        Returns the Stripe subscription object.
        """
        if not self.stripe_subscription_id:
            raise ValueError("No Stripe subscription ID found")
        
        try:
            import stripe
            from django.conf import settings
            
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Retrieve subscription from Stripe
            stripe_subscription = stripe.Subscription.retrieve(self.stripe_subscription_id)
            
            # Update local status
            self.status = stripe_subscription.status
            self.save(update_fields=['status', 'updated_at'])
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Synced subscription {self.id} from Stripe. Status: {self.status}")
            
            return stripe_subscription
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to sync subscription from Stripe: {str(e)}")
            raise
    
    def check_usage_limits(self):
        """Check if usage is within plan limits."""
        limits_exceeded = []
        
        if self.plan.max_users and self.current_users_count > self.plan.max_users:
            limits_exceeded.append('users')
        
        if self.plan.max_equipment and self.current_equipment_count > self.plan.max_equipment:
            limits_exceeded.append('equipment')
        
        if self.plan.max_storage_gb and self.current_storage_gb > self.plan.max_storage_gb:
            limits_exceeded.append('storage')
        
        if self.plan.max_api_calls_per_month and self.current_api_calls_this_month > self.plan.max_api_calls_per_month:
            limits_exceeded.append('api_calls')
        
        return limits_exceeded
    
    def update_usage_counts(self):
        """Update current usage counts."""
        try:
            # User model is in SHARED_APPS (public schema), so we need to count via TenantMember
            from apps.tenants.models import TenantMember
            
            # Count active tenant members (users belong to tenant via TenantMember)
            self.current_users_count = TenantMember.objects.filter(
                tenant=self.tenant,
                is_active=True
            ).count()
            
            # Equipment is in TENANT_APPS (tenant schema), so we need to switch schema context
            if hasattr(self.tenant, 'schema_name'):
                from django_tenants.utils import schema_context
                with schema_context(self.tenant.schema_name):
                    # Try to count equipment, but don't fail if table doesn't exist
                    try:
                        from apps.equipment.models import Equipment
                        self.current_equipment_count = Equipment.objects.count()
                    except Exception:
                        self.current_equipment_count = 0
            else:
                # For single-tenant setup (SQLite development)
                try:
                    from apps.equipment.models import Equipment
                    self.current_equipment_count = Equipment.objects.count()
                except:
                    self.current_equipment_count = 0
            
            # TODO: Calculate storage usage
            self.save(update_fields=['current_users_count', 'current_equipment_count'])
        except Exception as e:
            # Don't fail subscription creation if usage count fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to update usage counts: {str(e)}")
