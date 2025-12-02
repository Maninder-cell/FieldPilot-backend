"""
Tenant Models with django-tenants for schema-per-tenant multi-tenancy

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    """
    Tenant/Company model - represents an organization using the platform.
    Uses django-tenants for schema-per-tenant isolation.
    
    Note: We override the default auto-incrementing id from TenantMixin
    to use UUID as primary key (existing database constraint).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Company/Organization name")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly identifier")
    
    # Company information
    company_email = models.EmailField(blank=True)
    company_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    company_size = models.CharField(
        max_length=50,
        choices=[
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('201-500', '201-500 employees'),
            ('500+', '500+ employees'),
        ],
        blank=True
    )
    industry = models.CharField(max_length=100, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Trial information
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Onboarding
    onboarding_completed = models.BooleanField(default=False)
    onboarding_step = models.IntegerField(default=1)  # Track onboarding progress
    
    # Settings (JSON field for flexible configuration)
    settings = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Generate slug from name if not provided
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Generate schema_name from slug if not provided
        # Schema names must be lowercase and use underscores
        if not self.schema_name:
            self.schema_name = self.slug.replace('-', '_').lower()
        
        # Set auto_create_schema to True by default
        if not hasattr(self, 'auto_create_schema'):
            self.auto_create_schema = True
        
        super().save(*args, **kwargs)
    
    @property
    def is_trial_active(self):
        """
        Check if trial is still active.
        
        Note: This checks the tenant-level trial (before subscription creation).
        Once a subscription is created, check the subscription's trial status instead,
        as Stripe is the source of truth for subscription trials.
        """
        if not self.trial_ends_at:
            return False
        
        # Check if tenant has a subscription
        if hasattr(self, 'subscription') and self.subscription:
            # If subscription exists, check Stripe subscription trial status
            # This handles cases where time is simulated in Stripe
            try:
                if self.subscription.stripe_subscription_id:
                    # Sync from Stripe to get accurate trial status
                    self.subscription.sync_from_stripe()
                    return self.subscription.is_trial
            except Exception:
                # Fall back to local check if Stripe sync fails
                pass
        
        # For tenants without subscriptions, check local trial_ends_at
        return timezone.now() < self.trial_ends_at
    
    def start_trial(self, days=14):
        """Start trial period."""
        self.trial_ends_at = timezone.now() + timezone.timedelta(days=days)
        self.save()
    
    def extend_trial(self, days=14):
        """Extend trial period."""
        if self.trial_ends_at:
            self.trial_ends_at += timezone.timedelta(days=days)
        else:
            self.trial_ends_at = timezone.now() + timezone.timedelta(days=days)
        self.save()


class Domain(DomainMixin):
    """
    Domain model for tenant routing.
    Links domains to tenants for schema-per-tenant routing.
    """
    class Meta:
        db_table = 'tenants_domains'
        verbose_name = 'Domain'
        verbose_name_plural = 'Domains'
    
    def __str__(self):
        return f"{self.domain} ({'primary' if self.is_primary else 'secondary'})"


class TenantMember(models.Model):
    """
    Link users to tenants with roles.
    This is the source of truth for user roles in a multi-tenant system.
    A user can have different roles in different tenants.
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('technician', 'Technician'),
        ('customer', 'Customer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    
    # Tenant-specific employee information (moved from User model)
    employee_id = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tenant_members'
        unique_together = ['tenant', 'user']
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['tenant', 'user', 'is_active']),
            models.Index(fields=['role']),
            models.Index(fields=['employee_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.tenant.name} ({self.role})"
    
    @property
    def is_owner(self):
        """Check if member is owner."""
        return self.role == 'owner'
    
    @property
    def is_admin(self):
        """Check if member is admin or owner."""
        return self.role in ['owner', 'admin']
    
    @property
    def is_manager(self):
        """Check if member is manager, admin, or owner."""
        return self.role in ['owner', 'admin', 'manager']
    
    @property
    def is_technician(self):
        """Check if member is technician."""
        return self.role == 'technician'
    
    @property
    def is_customer(self):
        """Check if member is customer."""
        return self.role == 'customer'
    
    def generate_employee_id(self):
        """Generate unique employee ID within this tenant."""
        if not self.employee_id:
            role_prefix = {
                'owner': 'OWN',
                'admin': 'ADM',
                'manager': 'MGR',
                'employee': 'EMP',
                'technician': 'TEC',
                'customer': 'CUS',
            }.get(self.role, 'USR')
            
            # Find the highest existing employee ID for this role prefix in this tenant
            existing_ids = TenantMember.objects.filter(
                tenant=self.tenant,
                employee_id__startswith=role_prefix
            ).values_list('employee_id', flat=True)
            
            if existing_ids:
                numbers = []
                for emp_id in existing_ids:
                    try:
                        num = int(emp_id.replace(role_prefix, ''))
                        numbers.append(num)
                    except (ValueError, AttributeError):
                        continue
                
                next_num = max(numbers) + 1 if numbers else 1
            else:
                next_num = 1
            
            self.employee_id = f"{role_prefix}{next_num:04d}"
    
    def save(self, *args, **kwargs):
        # Generate employee ID if not set
        if not self.employee_id:
            self.generate_employee_id()
        
        super().save(*args, **kwargs)


class TenantSettings(models.Model):
    """
    Extended tenant settings model for complex configurations.
    """
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='tenant_settings')
    
    # Branding
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    secondary_color = models.CharField(max_length=7, default='#1F2937')
    
    # Features
    features_enabled = models.JSONField(default=dict)
    
    # Notifications
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Timezone and locale
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    date_format = models.CharField(max_length=20, default='YYYY-MM-DD')
    
    # Business hours
    business_hours = models.JSONField(default=dict)  # Store business hours per day
    
    # Custom fields configuration
    custom_fields = models.JSONField(default=dict)
    
    # Integration settings
    integrations = models.JSONField(default=dict)
    
    # Labor and Wage Settings
    normal_working_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8.00,
        help_text="Normal working hours per day (e.g., 8.00 for 8 hours)"
    )
    default_normal_hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        help_text="Default hourly rate for normal hours (in tenant's currency)"
    )
    default_overtime_hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=75.00,
        help_text="Default hourly rate for overtime hours (in tenant's currency)"
    )
    overtime_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.50,
        help_text="Overtime rate multiplier (e.g., 1.5 for time-and-a-half)"
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency code (ISO 4217, e.g., USD, EUR, GBP)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"Settings for {self.tenant.name}"



class TenantInvitation(models.Model):
    """
    Pending invitations for users to join a tenant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Admin'),
            ('manager', 'Manager'),
            ('employee', 'Employee'),
        ],
        default='employee'
    )
    invited_by = models.ForeignKey('authentication.User', on_delete=models.SET_NULL, null=True, related_name='sent_invitations')
    
    # Invitation token for verification
    token = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('expired', 'Expired'),
            ('revoked', 'Revoked'),
        ],
        default='pending'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tenant_invitations'
        unique_together = ['tenant', 'email']
        ordering = ['-created_at']
        verbose_name = 'Tenant Invitation'
        verbose_name_plural = 'Tenant Invitations'
    
    def __str__(self):
        return f"Invitation for {self.email} to {self.tenant.name}"
    
    def is_valid(self):
        """Check if invitation is still valid."""
        return (
            self.status == 'pending' and
            timezone.now() < self.expires_at
        )
    
    def accept(self, user):
        """Mark invitation as accepted."""
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()
        
        # Create tenant membership
        TenantMember.objects.create(
            tenant=self.tenant,
            user=user,
            role=self.role
        )


class TechnicianWageRate(models.Model):
    """
    Technician-specific wage rates with effective date tracking.
    Allows different rates for different technicians and tracks rate history.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='wage_rates',
        help_text="Technician this rate applies to (role validated via TenantMember)"
    )
    
    # Wage Rates
    normal_hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Hourly rate for normal hours"
    )
    overtime_hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Hourly rate for overtime hours"
    )
    
    # Effective Dates
    effective_from = models.DateField(
        db_index=True,
        help_text="Date when this rate becomes effective"
    )
    effective_to = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Date when this rate expires (null = current rate)"
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this rate is currently active"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes about this rate change"
    )
    
    # Audit
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='wage_rates_created',
        help_text="User who created this rate"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'technician_wage_rates'
        verbose_name = 'Technician Wage Rate'
        verbose_name_plural = 'Technician Wage Rates'
        ordering = ['-effective_from', '-created_at']
        indexes = [
            models.Index(fields=['technician', 'effective_from']),
            models.Index(fields=['technician', 'is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        return f"{self.technician.full_name} - ${self.normal_hourly_rate}/hr (from {self.effective_from})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate technician role - check TenantMember instead of User.role
        if self.technician:
            from django.db import connection
            # Only validate role if we're in a tenant context
            if hasattr(connection, 'tenant') and connection.tenant:
                try:
                    member = TenantMember.objects.get(
                        tenant=connection.tenant,
                        user=self.technician,
                        is_active=True
                    )
                    if member.role != 'technician':
                        raise ValidationError({
                            'technician': 'Wage rates can only be set for technicians.'
                        })
                except TenantMember.DoesNotExist:
                    raise ValidationError({
                        'technician': 'User is not a member of this tenant.'
                    })
        
        # Validate effective dates
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValidationError({
                'effective_to': 'Effective to date must be after effective from date.'
            })
        
        # Validate rates are positive
        if self.normal_hourly_rate <= 0:
            raise ValidationError({
                'normal_hourly_rate': 'Normal hourly rate must be greater than zero.'
            })
        if self.overtime_hourly_rate <= 0:
            raise ValidationError({
                'overtime_hourly_rate': 'Overtime hourly rate must be greater than zero.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to run validation and manage active rates."""
        self.full_clean()
        
        # If this is a new active rate, deactivate other active rates for this technician
        if self.is_active and not self.effective_to:
            TechnicianWageRate.objects.filter(
                technician=self.technician,
                is_active=True,
                effective_to__isnull=True
            ).exclude(pk=self.pk).update(
                is_active=False,
                effective_to=self.effective_from
            )
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_rate_for_date(cls, technician, date):
        """
        Get the wage rate for a technician on a specific date.
        Returns the rate that was effective on that date, or None if not found.
        
        Args:
            technician: User instance (technician)
            date: Date to get rate for
            
        Returns:
            TechnicianWageRate instance or None
        """
        return cls.objects.filter(
            technician=technician,
            effective_from__lte=date,
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
        ).order_by('-effective_from').first()
    
    @classmethod
    def get_current_rate(cls, technician):
        """
        Get the current active wage rate for a technician.
        
        Args:
            technician: User instance (technician)
            
        Returns:
            TechnicianWageRate instance or None
        """
        return cls.objects.filter(
            technician=technician,
            is_active=True,
            effective_to__isnull=True
        ).order_by('-effective_from').first()
