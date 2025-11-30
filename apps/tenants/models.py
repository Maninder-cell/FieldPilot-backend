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
