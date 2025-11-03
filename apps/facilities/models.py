"""
Facilities Models

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from apps.core.models import SoftDeleteModel, AuditMixin, UUIDPrimaryKeyMixin


class Customer(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Customer model - represents external stakeholders who can be granted access to facilities,
    buildings, and equipment. Customers can be invited to the system and linked to a user account.
    """
    
    # Basic Information
    name = models.CharField(max_length=255, help_text="Customer name")
    email = models.EmailField(unique=True, help_text="Primary contact email")
    phone = models.CharField(max_length=20, blank=True, help_text="Contact phone number")
    company_name = models.CharField(max_length=255, blank=True, help_text="Company/Organization name")
    contact_person = models.CharField(max_length=255, blank=True, help_text="Primary contact person name")
    
    # Address Information
    address = models.TextField(blank=True, help_text="Full street address")
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    
    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Customer status"
    )
    
    # User Link (after invitation acceptance)
    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_profile',
        help_text="Linked user account after invitation acceptance"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes about the customer")
    
    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['company_name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate email format
        if self.email:
            self.email = self.email.lower().strip()
        
        # Ensure email is unique within non-deleted customers
        if self.email:
            existing = Customer.objects.filter(
                email=self.email
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError({
                    'email': 'A customer with this email already exists.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if customer is active."""
        return self.status == 'active' and not self.is_deleted
    
    @property
    def has_user_account(self):
        """Check if customer has a linked user account."""
        return self.user is not None
    
    def activate(self):
        """Activate the customer."""
        self.status = 'active'
        self.save(update_fields=['status', 'updated_at'])
    
    def deactivate(self):
        """Deactivate the customer."""
        self.status = 'inactive'
        self.save(update_fields=['status', 'updated_at'])


class CustomerInvitation(UUIDPrimaryKeyMixin, models.Model):
    """
    Customer invitation model - manages the invitation workflow for customers
    to access the system. Generates unique tokens and tracks invitation status.
    """
    
    # Relationships
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='invitations',
        help_text="Customer being invited"
    )
    invited_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='customer_invitations_sent',
        help_text="User who sent the invitation"
    )
    
    # Invitation Details
    email = models.EmailField(help_text="Email address for invitation")
    token = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique invitation token"
    )
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Invitation status"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="Invitation expiration date")
    accepted_at = models.DateTimeField(null=True, blank=True, help_text="When invitation was accepted")
    
    class Meta:
        db_table = 'customer_invitations'
        verbose_name = 'Customer Invitation'
        verbose_name_plural = 'Customer Invitations'
        ordering = ['-created_at']
        unique_together = [['customer', 'email']]
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['token']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Invitation for {self.email} - {self.status}"
    
    def is_valid(self):
        """
        Check if invitation is still valid.
        
        Returns:
            bool: True if invitation is pending and not expired
        """
        return (
            self.status == 'pending' and
            timezone.now() < self.expires_at
        )
    
    def accept(self, user):
        """
        Accept the invitation and link user to customer.
        
        Args:
            user: User instance to link to the customer
        
        Raises:
            ValidationError: If invitation is not valid
        """
        if not self.is_valid():
            raise ValidationError("This invitation has expired or is no longer valid.")
        
        # Update invitation status
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])
        
        # Link user to customer
        self.customer.user = user
        self.customer.status = 'active'
        self.customer.save(update_fields=['user', 'status', 'updated_at'])
        
        # Update user role to customer if not already
        if user.role != 'customer':
            user.role = 'customer'
            user.save(update_fields=['role'])
    
    def revoke(self):
        """
        Revoke the invitation.
        """
        self.status = 'revoked'
        self.save(update_fields=['status'])
    
    def mark_expired(self):
        """
        Mark invitation as expired.
        """
        self.status = 'expired'
        self.save(update_fields=['status'])
    
    @classmethod
    def generate_token(cls):
        """
        Generate a unique invitation token.
        
        Returns:
            str: Unique token string
        """
        import secrets
        return secrets.token_urlsafe(32)
    
    def save(self, *args, **kwargs):
        """
        Override save to generate token if not provided.
        """
        if not self.token:
            self.token = self.generate_token()
        
        # Set expiration if not provided (default 7 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        
        super().save(*args, **kwargs)



class Facility(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Facility model - represents physical sites or locations (top-level in hierarchy).
    Facilities can contain multiple buildings and can be assigned to customers.
    """
    
    # Basic Information
    name = models.CharField(max_length=255, help_text="Facility name")
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique facility code (auto-generated)"
    )
    
    # Facility Type
    FACILITY_TYPE_CHOICES = [
        ('warehouse', 'Warehouse'),
        ('office', 'Office'),
        ('factory', 'Factory'),
        ('retail', 'Retail'),
        ('datacenter', 'Data Center'),
        ('other', 'Other'),
    ]
    facility_type = models.CharField(
        max_length=50,
        choices=FACILITY_TYPE_CHOICES,
        default='other',
        db_index=True,
        help_text="Type of facility"
    )
    
    description = models.TextField(blank=True, help_text="Facility description")
    
    # Address Information
    address = models.TextField(blank=True, help_text="Full street address")
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    
    # Geolocation
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )
    
    # Contact Information
    contact_name = models.CharField(max_length=255, blank=True, help_text="Primary contact name")
    contact_email = models.EmailField(blank=True, help_text="Primary contact email")
    contact_phone = models.CharField(max_length=20, blank=True, help_text="Primary contact phone")
    
    # Operational Status
    OPERATIONAL_STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('under_construction', 'Under Construction'),
        ('maintenance', 'Maintenance'),
        ('closed', 'Closed'),
    ]
    operational_status = models.CharField(
        max_length=50,
        choices=OPERATIONAL_STATUS_CHOICES,
        default='operational',
        db_index=True,
        help_text="Current operational status"
    )
    
    # Physical Details
    square_footage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total square footage"
    )
    year_built = models.IntegerField(null=True, blank=True, help_text="Year facility was built")
    
    # Customer Assignment
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facilities',
        help_text="Customer assigned to this facility"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes")
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for additional data"
    )
    
    # Location (polymorphic relationship)
    locations = GenericRelation('Location', related_query_name='facility')
    
    class Meta:
        db_table = 'facilities'
        verbose_name = 'Facility'
        verbose_name_plural = 'Facilities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['facility_type']),
            models.Index(fields=['operational_status']),
            models.Index(fields=['customer']),
            models.Index(fields=['city', 'state']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate latitude range
        if self.latitude is not None:
            if not (-90 <= self.latitude <= 90):
                raise ValidationError({
                    'latitude': 'Latitude must be between -90 and 90 degrees.'
                })
        
        # Validate longitude range
        if self.longitude is not None:
            if not (-180 <= self.longitude <= 180):
                raise ValidationError({
                    'longitude': 'Longitude must be between -180 and 180 degrees.'
                })
        
        # Validate customer is active if assigned
        if self.customer and not self.customer.is_active:
            raise ValidationError({
                'customer': 'Cannot assign an inactive customer to a facility.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to generate code and run validation.
        """
        # Generate facility code if not provided
        if not self.code:
            self.code = self._generate_facility_code()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def _generate_facility_code(self):
        """
        Generate unique facility code in format: FAC-YYYY-NNNN
        
        Returns:
            str: Generated facility code
        """
        from django.db import transaction
        
        year = timezone.now().year
        
        with transaction.atomic():
            # Get the last facility code for this year
            last_facility = Facility.all_objects.filter(
                code__startswith=f'FAC-{year}-'
            ).order_by('-code').first()
            
            if last_facility:
                # Extract number from last code and increment
                try:
                    last_number = int(last_facility.code.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
            
            # Format: FAC-YYYY-NNNN
            return f'FAC-{year}-{next_number:04d}'
    
    @property
    def is_operational(self):
        """Check if facility is operational."""
        return self.operational_status == 'operational' and not self.is_deleted
    
    @property
    def buildings_count(self):
        """Get count of buildings in this facility."""
        return self.buildings.count()
    
    @property
    def equipment_count(self):
        """Get count of all equipment in this facility (across all buildings)."""
        from apps.equipment.models import Equipment
        return Equipment.objects.filter(building__facility=self).count()
    
    def delete(self, using=None, keep_parents=False, hard=False):
        """
        Override delete to cascade soft delete to buildings and equipment.
        """
        if not hard:
            # Soft delete all buildings (which will cascade to equipment)
            for building in self.buildings.all():
                building.delete()
        
        super().delete(using=using, keep_parents=keep_parents, hard=hard)



class Building(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Building model - represents structures within facilities.
    Buildings belong to a facility and can contain multiple equipment items.
    """
    
    # Relationships
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name='buildings',
        help_text="Parent facility"
    )
    
    # Basic Information
    name = models.CharField(max_length=255, help_text="Building name")
    code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Building code (unique within facility)"
    )
    
    # Building Type
    BUILDING_TYPE_CHOICES = [
        ('office', 'Office'),
        ('warehouse', 'Warehouse'),
        ('production', 'Production'),
        ('storage', 'Storage'),
        ('laboratory', 'Laboratory'),
        ('other', 'Other'),
    ]
    building_type = models.CharField(
        max_length=50,
        choices=BUILDING_TYPE_CHOICES,
        default='other',
        db_index=True,
        help_text="Type of building"
    )
    
    description = models.TextField(blank=True, help_text="Building description")
    
    # Physical Details
    floor_count = models.IntegerField(null=True, blank=True, help_text="Number of floors")
    square_footage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total square footage"
    )
    construction_year = models.IntegerField(null=True, blank=True, help_text="Year building was constructed")
    
    # Address (if different from facility)
    address = models.TextField(blank=True, help_text="Building address if different from facility")
    
    # Contact Information
    contact_name = models.CharField(max_length=255, blank=True, help_text="Building contact name")
    contact_email = models.EmailField(blank=True, help_text="Building contact email")
    contact_phone = models.CharField(max_length=20, blank=True, help_text="Building contact phone")
    
    # Operational Status
    OPERATIONAL_STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('under_construction', 'Under Construction'),
        ('maintenance', 'Maintenance'),
        ('closed', 'Closed'),
    ]
    operational_status = models.CharField(
        max_length=50,
        choices=OPERATIONAL_STATUS_CHOICES,
        default='operational',
        db_index=True,
        help_text="Current operational status"
    )
    
    # Customer Assignment
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='buildings',
        help_text="Customer assigned to this building"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes")
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for additional data"
    )
    
    # Location (polymorphic relationship)
    locations = GenericRelation('Location', related_query_name='building')
    
    class Meta:
        db_table = 'buildings'
        verbose_name = 'Building'
        verbose_name_plural = 'Buildings'
        ordering = ['-created_at']
        unique_together = [['facility', 'code']]
        indexes = [
            models.Index(fields=['facility', 'code']),
            models.Index(fields=['building_type']),
            models.Index(fields=['operational_status']),
            models.Index(fields=['customer']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code}) - {self.facility.name}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate parent facility is active
        if self.facility and not self.facility.is_operational:
            raise ValidationError({
                'facility': 'Cannot create building in a non-operational facility.'
            })
        
        # Validate customer is active if assigned
        if self.customer and not self.customer.is_active:
            raise ValidationError({
                'customer': 'Cannot assign an inactive customer to a building.'
            })
        
        # Validate code is unique within facility
        if self.facility and self.code:
            existing = Building.objects.filter(
                facility=self.facility,
                code=self.code
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError({
                    'code': 'A building with this code already exists in this facility.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to generate code and run validation.
        """
        # Generate building code if not provided
        if not self.code:
            self.code = self._generate_building_code()
        
        # Inherit customer from facility if not specified
        if not self.customer and self.facility and self.facility.customer:
            self.customer = self.facility.customer
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def _generate_building_code(self):
        """
        Generate unique building code within facility in format: BLD-NNNN
        
        Returns:
            str: Generated building code
        """
        from django.db import transaction
        
        with transaction.atomic():
            # Get the last building code for this facility
            last_building = Building.all_objects.filter(
                facility=self.facility,
                code__startswith='BLD-'
            ).order_by('-code').first()
            
            if last_building:
                # Extract number from last code and increment
                try:
                    last_number = int(last_building.code.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
            
            # Format: BLD-NNNN
            return f'BLD-{next_number:04d}'
    
    @property
    def is_operational(self):
        """Check if building is operational."""
        return self.operational_status == 'operational' and not self.is_deleted
    
    @property
    def equipment_count(self):
        """Get count of equipment in this building."""
        return self.equipment_items.count()
    
    def delete(self, using=None, keep_parents=False, hard=False):
        """
        Override delete to cascade soft delete to equipment.
        """
        if not hard:
            # Soft delete all equipment
            for equipment in self.equipment_items.all():
                equipment.delete()
        
        super().delete(using=using, keep_parents=keep_parents, hard=hard)



class Location(UUIDPrimaryKeyMixin, models.Model):
    """
    Location model - provides flexible location tagging for any entity using polymorphic relationships.
    Can be attached to facilities, buildings, equipment, tasks, or any other model.
    """
    
    # Polymorphic Relationship (Generic Foreign Key)
    from django.contrib.contenttypes.fields import GenericForeignKey
    from django.contrib.contenttypes.models import ContentType
    
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Type of entity this location is attached to"
    )
    object_id = models.UUIDField(help_text="ID of the entity this location is attached to")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Location Information
    name = models.CharField(max_length=255, help_text="Location name")
    description = models.TextField(blank=True, help_text="Location description")
    
    # Geolocation
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )
    
    # Address
    address = models.TextField(blank=True, help_text="Physical address")
    
    # Indoor Location Details
    floor = models.CharField(max_length=50, blank=True, help_text="Floor level (e.g., '3rd Floor', 'Basement')")
    room = models.CharField(max_length=50, blank=True, help_text="Room number or name")
    zone = models.CharField(max_length=50, blank=True, help_text="Zone or area designation")
    
    # Additional Information
    additional_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional location information"
    )
    
    # Audit Fields
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locations_created',
        help_text="User who created this location"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'locations'
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
        ordering = ['-created_at']
        unique_together = [['content_type', 'object_id']]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.content_type.model}"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate latitude range
        if self.latitude is not None:
            if not (-90 <= self.latitude <= 90):
                raise ValidationError({
                    'latitude': 'Latitude must be between -90 and 90 degrees.'
                })
        
        # Validate longitude range
        if self.longitude is not None:
            if not (-180 <= self.longitude <= 180):
                raise ValidationError({
                    'longitude': 'Longitude must be between -180 and 180 degrees.'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation.
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def has_coordinates(self):
        """Check if location has geolocation coordinates."""
        return self.latitude is not None and self.longitude is not None
    
    @property
    def full_location(self):
        """Get full location string."""
        parts = []
        if self.room:
            parts.append(f"Room {self.room}")
        if self.floor:
            parts.append(self.floor)
        if self.zone:
            parts.append(f"Zone {self.zone}")
        if self.address:
            parts.append(self.address)
        return ', '.join(parts) if parts else self.name
