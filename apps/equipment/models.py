"""
Equipment Models

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericRelation
from apps.core.models import SoftDeleteModel, AuditMixin, UUIDPrimaryKeyMixin


class EquipmentNumberSequence(models.Model):
    """
    Atomic counter for generating sequential equipment numbers.
    One sequence per tenant to ensure uniqueness within tenant schema.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_number = models.IntegerField(default=0, help_text="Last generated equipment number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'equipment_number_sequence'
        verbose_name = 'Equipment Number Sequence'
        verbose_name_plural = 'Equipment Number Sequences'
    
    def __str__(self):
        return f"Equipment Sequence - Last: {self.last_number}"
    
    @classmethod
    def generate_next_number(cls):
        """
        Generate the next equipment number in a thread-safe manner.
        Uses select_for_update to lock the row during transaction.
        
        Returns:
            str: Formatted equipment number (e.g., 'EQ-000001')
        """
        with transaction.atomic():
            # Get or create the sequence (there should only be one per tenant)
            sequence, created = cls.objects.select_for_update().get_or_create(
                pk=cls.objects.first().pk if cls.objects.exists() else uuid.uuid4(),
                defaults={'last_number': 0}
            )
            
            # Increment the counter
            sequence.last_number += 1
            next_number = sequence.last_number
            sequence.save(update_fields=['last_number', 'updated_at'])
            
            # Format as EQ-NNNNNN (e.g., EQ-000001)
            return f"EQ-{next_number:06d}"



class Equipment(UUIDPrimaryKeyMixin, SoftDeleteModel, AuditMixin):
    """
    Equipment model - represents individual assets within buildings.
    Equipment has auto-generated sequential numbers and can be assigned to customers.
    """
    
    # Relationships
    building = models.ForeignKey(
        'facilities.Building',
        on_delete=models.CASCADE,
        related_name='equipment_items',
        help_text="Parent building"
    )
    
    # Equipment Number (auto-generated)
    equipment_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique equipment number (auto-generated)"
    )
    
    # Basic Information
    name = models.CharField(max_length=255, help_text="Equipment name")
    
    # Equipment Type
    EQUIPMENT_TYPE_CHOICES = [
        ('hvac', 'HVAC'),
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing'),
        ('machinery', 'Machinery'),
        ('it', 'IT Equipment'),
        ('safety', 'Safety Equipment'),
        ('other', 'Other'),
    ]
    equipment_type = models.CharField(
        max_length=50,
        choices=EQUIPMENT_TYPE_CHOICES,
        default='other',
        db_index=True,
        help_text="Type of equipment"
    )
    
    # Manufacturer Information
    manufacturer = models.CharField(max_length=255, blank=True, help_text="Equipment manufacturer")
    model = models.CharField(max_length=255, blank=True, help_text="Equipment model")
    serial_number = models.CharField(max_length=255, blank=True, help_text="Manufacturer serial number")
    
    description = models.TextField(blank=True, help_text="Equipment description")
    
    # Purchase Information
    purchase_date = models.DateField(null=True, blank=True, help_text="Date of purchase")
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Purchase price"
    )
    warranty_expiration = models.DateField(null=True, blank=True, help_text="Warranty expiration date")
    installation_date = models.DateField(null=True, blank=True, help_text="Installation date")
    
    # Operational Status
    OPERATIONAL_STATUS_CHOICES = [
        ('operational', 'Operational'),
        ('maintenance', 'Maintenance'),
        ('broken', 'Broken'),
        ('retired', 'Retired'),
    ]
    operational_status = models.CharField(
        max_length=50,
        choices=OPERATIONAL_STATUS_CHOICES,
        default='operational',
        db_index=True,
        help_text="Current operational status"
    )
    
    # Condition
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    condition = models.CharField(
        max_length=50,
        choices=CONDITION_CHOICES,
        default='good',
        help_text="Physical condition"
    )
    
    # Technical Specifications
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Technical specifications"
    )
    
    # Customer Assignment
    customer = models.ForeignKey(
        'facilities.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_items',
        help_text="Customer assigned to this equipment"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, help_text="Internal notes")
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom fields for additional data"
    )
    
    # Location (polymorphic relationship)
    locations = GenericRelation('facilities.Location', related_query_name='equipment')
    
    class Meta:
        db_table = 'equipment'
        verbose_name = 'Equipment'
        verbose_name_plural = 'Equipment'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['equipment_number']),
            models.Index(fields=['building']),
            models.Index(fields=['equipment_type']),
            models.Index(fields=['manufacturer']),
            models.Index(fields=['operational_status']),
            models.Index(fields=['customer']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.equipment_number})"
    
    def clean(self):
        """
        Validate model data.
        """
        super().clean()
        
        # Validate parent building is operational
        if self.building and not self.building.is_operational:
            raise ValidationError({
                'building': 'Cannot create equipment in a non-operational building.'
            })
        
        # Validate customer is active if assigned
        if self.customer and not self.customer.is_active:
            raise ValidationError({
                'customer': 'Cannot assign an inactive customer to equipment.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to generate equipment number and run validation.
        """
        # Generate equipment number if not provided
        if not self.equipment_number:
            self.equipment_number = EquipmentNumberSequence.generate_next_number()
        
        # Inherit customer from building or facility if not specified
        if not self.customer:
            if self.building.customer:
                self.customer = self.building.customer
            elif self.building.facility.customer:
                self.customer = self.building.facility.customer
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_operational(self):
        """Check if equipment is operational."""
        return self.operational_status == 'operational' and not self.is_deleted
    
    @property
    def facility(self):
        """Get the facility this equipment belongs to."""
        return self.building.facility if self.building else None
    
    @property
    def is_under_warranty(self):
        """Check if equipment is still under warranty."""
        if self.warranty_expiration:
            from django.utils import timezone
            return timezone.now().date() < self.warranty_expiration
        return False
