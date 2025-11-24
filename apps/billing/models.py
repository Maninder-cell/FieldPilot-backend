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
    Tenant subscriptions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        'tenants.Tenant', 
        on_delete=models.CASCADE, 
        related_name='subscription'
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    
    # Stripe integration
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    
    # Subscription details
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
    
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        default='monthly'
    )
    
    # Billing periods
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    
    # Cancellation
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
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
    
    @property
    def days_until_renewal(self):
        """Days until next billing cycle."""
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0
    
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
        from django.db import transaction
        
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


class Invoice(models.Model):
    """
    Billing invoices.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', 
        on_delete=models.CASCADE, 
        related_name='invoices'
    )
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE, 
        related_name='invoices',
        null=True, 
        blank=True
    )
    
    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Status
    status = models.CharField(
        max_length=50,
        choices=[
            ('draft', 'Draft'),
            ('open', 'Open'),
            ('paid', 'Paid'),
            ('void', 'Void'),
            ('uncollectible', 'Uncollectible'),
        ],
        default='draft'
    )
    
    # Dates
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Files
    invoice_pdf_url = models.URLField(blank=True)
    
    # Billing period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_invoices'
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.tenant.name}"
    
    def generate_invoice_number(self):
        """Generate unique invoice number."""
        if not self.invoice_number:
            year = timezone.now().year
            month = timezone.now().month
            
            # Get count of invoices this month
            count = Invoice.objects.filter(
                created_at__year=year,
                created_at__month=month
            ).count() + 1
            
            self.invoice_number = f"FP-{year}{month:02d}-{count:04d}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.generate_invoice_number()
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment records.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='payments',
        null=True, 
        blank=True
    )
    
    # Stripe integration
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Payment method
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ('card', 'Credit Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('ach', 'ACH'),
            ('wire', 'Wire Transfer'),
        ],
        default='card'
    )
    
    # Status
    status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ('canceled', 'Canceled'),
            ('refunded', 'Refunded'),
        ],
        default='pending'
    )
    
    # Failure information
    failure_code = models.CharField(max_length=100, blank=True)
    failure_message = models.TextField(blank=True)
    
    # Timestamps
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'billing_payments'
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"Payment {self.amount} {self.currency} - {self.tenant.name}"


class UsageRecord(models.Model):
    """
    Track usage for billing purposes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', 
        on_delete=models.CASCADE, 
        related_name='usage_records'
    )
    
    # Usage metrics
    metric_name = models.CharField(max_length=100)  # users, equipment, storage, api_calls
    value = models.DecimalField(max_digits=15, decimal_places=2)
    unit = models.CharField(max_length=50)  # count, gb, calls
    
    # Time period
    recorded_at = models.DateTimeField(default=timezone.now)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'billing_usage_records'
        ordering = ['-recorded_at']
        verbose_name = 'Usage Record'
        verbose_name_plural = 'Usage Records'
        indexes = [
            models.Index(fields=['tenant', 'metric_name', 'recorded_at']),
        ]
    
    def __str__(self):
        return f"{self.tenant.name} - {self.metric_name}: {self.value} {self.unit}"