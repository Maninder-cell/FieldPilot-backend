"""
Facilities Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Customer, CustomerInvitation, Facility, Building, Location
from apps.authentication.serializers import UserSerializer


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for Customer model with all fields.
    """
    user = UserSerializer(read_only=True)
    is_active = serializers.ReadOnlyField()
    has_user_account = serializers.ReadOnlyField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'email', 'phone', 'company_name', 'contact_person',
            'address', 'city', 'state', 'zip_code', 'country', 'status',
            'user', 'notes', 'is_active', 'has_user_account',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class CreateCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new customer.
    """
    class Meta:
        model = Customer
        fields = [
            'name', 'email', 'phone', 'company_name', 'contact_person',
            'address', 'city', 'state', 'zip_code', 'country', 'status', 'notes'
        ]
    
    def validate_email(self, value):
        """
        Validate email is unique among non-deleted customers.
        """
        if value:
            value = value.lower().strip()
            
            # Check for existing non-deleted customers with this email
            existing = Customer.objects.filter(email=value)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A customer with this email already exists."
                )
        
        return value


class UpdateCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for updating customer information.
    """
    class Meta:
        model = Customer
        fields = [
            'name', 'email', 'phone', 'company_name', 'contact_person',
            'address', 'city', 'state', 'zip_code', 'country', 'status', 'notes'
        ]
        extra_kwargs = {
            'name': {'required': False},
            'email': {'required': False},
            'phone': {'required': False},
            'company_name': {'required': False},
            'contact_person': {'required': False},
            'address': {'required': False},
            'city': {'required': False},
            'state': {'required': False},
            'zip_code': {'required': False},
            'country': {'required': False},
            'status': {'required': False},
            'notes': {'required': False},
        }
    
    def validate_email(self, value):
        """
        Validate email is unique among non-deleted customers.
        """
        if value:
            value = value.lower().strip()
            
            # Check for existing non-deleted customers with this email
            existing = Customer.objects.filter(email=value)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "A customer with this email already exists."
                )
        
        return value


class CustomerInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomerInvitation model.
    """
    customer = CustomerSerializer(read_only=True)
    invited_by = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerInvitation
        fields = [
            'id', 'customer', 'email', 'token', 'status',
            'invited_by', 'is_valid',
            'created_at', 'expires_at', 'accepted_at'
        ]
        read_only_fields = [
            'id', 'token', 'status', 'created_at',
            'expires_at', 'accepted_at'
        ]
    
    def get_invited_by(self, obj):
        """Get invited by user's full name."""
        if obj.invited_by:
            return obj.invited_by.full_name
        return None
    
    def get_is_valid(self, obj):
        """Check if invitation is still valid."""
        return obj.is_valid()



class InviteCustomerSerializer(serializers.Serializer):
    """
    Serializer for inviting a customer.
    """
    customer_id = serializers.UUIDField(required=True)
    email = serializers.EmailField(required=True)
    message = serializers.CharField(required=False, allow_blank=True)
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is not deleted.
        """
        try:
            customer = Customer.objects.get(pk=value)
            self.customer = customer
            return value
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer not found.")
    
    def validate(self, data):
        """
        Validate invitation data.
        """
        customer = self.customer
        email = data['email'].lower().strip()
        
        # Check if customer already has a user account
        if customer.user:
            raise serializers.ValidationError({
                'customer_id': 'This customer already has a user account.'
            })
        
        # Check if there's already a pending invitation
        existing_invitation = CustomerInvitation.objects.filter(
            customer=customer,
            email=email,
            status='pending'
        ).first()
        
        if existing_invitation and existing_invitation.is_valid():
            raise serializers.ValidationError({
                'email': 'A pending invitation already exists for this email.'
            })
        
        data['email'] = email
        return data


class AcceptInvitationSerializer(serializers.Serializer):
    """
    Serializer for accepting a customer invitation.
    """
    token = serializers.CharField(required=True)
    tenant_slug = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """
        Validate invitation token exists and is valid.
        Multi-tenant aware: searches across all tenant schemas.
        """
        from django.db import connection
        from django_tenants.utils import schema_context
        from apps.tenants.models import Tenant
        
        token = attrs.get('token')
        tenant_slug = attrs.get('tenant_slug')
        
        # If tenant_slug is provided, search only in that tenant
        if tenant_slug:
            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
                with schema_context(tenant.schema_name):
                    invitation = CustomerInvitation.objects.get(token=token)
                    
                    if not invitation.is_valid():
                        raise serializers.ValidationError({
                            'token': "This invitation has expired or is no longer valid."
                        })
                    
                    self.invitation = invitation
                    self.tenant = tenant
                    return attrs
            except Tenant.DoesNotExist:
                raise serializers.ValidationError({
                    'tenant_slug': "Invalid tenant."
                })
            except CustomerInvitation.DoesNotExist:
                raise serializers.ValidationError({
                    'token': "Invalid invitation token."
                })
        
        # If no tenant_slug, search across all tenants
        tenants = Tenant.objects.filter(is_active=True)
        
        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    invitation = CustomerInvitation.objects.get(token=token)
                    
                    if not invitation.is_valid():
                        raise serializers.ValidationError({
                            'token': "This invitation has expired or is no longer valid."
                        })
                    
                    self.invitation = invitation
                    self.tenant = tenant
                    return attrs
            except CustomerInvitation.DoesNotExist:
                continue
        
        # Token not found in any tenant
        raise serializers.ValidationError({
            'token': "Invalid invitation token."
        })
        
        return attrs



# Facility Serializers

class FacilitySerializer(serializers.ModelSerializer):
    """
    Serializer for Facility model with nested customer data.
    """
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    is_operational = serializers.ReadOnlyField()
    buildings_count = serializers.ReadOnlyField()
    equipment_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Facility
        fields = [
            'id', 'name', 'code', 'facility_type', 'description',
            'address', 'city', 'state', 'zip_code', 'country',
            'latitude', 'longitude', 'contact_name', 'contact_email', 'contact_phone',
            'operational_status', 'square_footage', 'year_built',
            'customer', 'customer_id', 'notes', 'custom_fields',
            'is_operational', 'buildings_count', 'equipment_count',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'code', 'created_by', 'created_at', 'updated_at']


class CreateFacilitySerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new facility.
    """
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Facility
        fields = [
            'name', 'facility_type', 'description',
            'address', 'city', 'state', 'zip_code', 'country',
            'latitude', 'longitude', 'contact_name', 'contact_email', 'contact_phone',
            'operational_status', 'square_footage', 'year_built',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            try:
                customer = Customer.objects.get(pk=value)
                if not customer.is_active:
                    raise serializers.ValidationError("Customer must be active.")
                self.customer = customer
                return value
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found.")
        return value
    
    def validate_latitude(self, value):
        """Validate latitude range."""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value
    
    def validate_longitude(self, value):
        """Validate longitude range."""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value
    
    def create(self, validated_data):
        """Create facility with customer assignment."""
        customer_id = validated_data.pop('customer_id', None)
        
        facility = Facility(**validated_data)
        if customer_id and hasattr(self, 'customer'):
            facility.customer = self.customer
        
        facility.save()
        return facility


class UpdateFacilitySerializer(serializers.ModelSerializer):
    """
    Serializer for updating facility information.
    """
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Facility
        fields = [
            'name', 'facility_type', 'description',
            'address', 'city', 'state', 'zip_code', 'country',
            'latitude', 'longitude', 'contact_name', 'contact_email', 'contact_phone',
            'operational_status', 'square_footage', 'year_built',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            try:
                customer = Customer.objects.get(pk=value)
                if not customer.is_active:
                    raise serializers.ValidationError("Customer must be active.")
                self.customer = customer
                return value
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found.")
        return value
    
    def validate_latitude(self, value):
        """Validate latitude range."""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value
    
    def validate_longitude(self, value):
        """Validate longitude range."""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value
    
    def update(self, instance, validated_data):
        """Update facility with customer assignment."""
        customer_id = validated_data.pop('customer_id', None)
        
        # Update customer if provided
        if customer_id is not None:
            if customer_id and hasattr(self, 'customer'):
                instance.customer = self.customer
            else:
                instance.customer = None
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class FacilityListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for facility list views.
    """
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    buildings_count = serializers.ReadOnlyField()
    equipment_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Facility
        fields = [
            'id', 'name', 'code', 'facility_type', 'city', 'state',
            'operational_status', 'customer_name', 'buildings_count',
            'equipment_count', 'created_at'
        ]




# Building Serializers

class BuildingSerializer(serializers.ModelSerializer):
    """
    Serializer for Building model with nested facility and customer data.
    """
    facility = FacilitySerializer(read_only=True)
    facility_id = serializers.UUIDField(write_only=True)
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    is_operational = serializers.ReadOnlyField()
    equipment_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Building
        fields = [
            'id', 'facility', 'facility_id', 'name', 'code', 'building_type', 'description',
            'floor_count', 'square_footage', 'construction_year', 'address',
            'contact_name', 'contact_email', 'contact_phone', 'operational_status',
            'customer', 'customer_id', 'notes', 'custom_fields',
            'is_operational', 'equipment_count',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'code', 'created_by', 'created_at', 'updated_at']


class CreateBuildingSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new building.
    """
    facility_id = serializers.UUIDField(required=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Building
        fields = [
            'facility_id', 'name', 'building_type', 'description',
            'floor_count', 'square_footage', 'construction_year', 'address',
            'contact_name', 'contact_email', 'contact_phone', 'operational_status',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_facility_id(self, value):
        """
        Validate facility exists and is operational.
        """
        try:
            facility = Facility.objects.get(pk=value)
            if not facility.is_operational:
                raise serializers.ValidationError("Facility must be operational.")
            self.facility = facility
            return value
        except Facility.DoesNotExist:
            raise serializers.ValidationError("Facility not found.")
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            try:
                customer = Customer.objects.get(pk=value)
                if not customer.is_active:
                    raise serializers.ValidationError("Customer must be active.")
                self.customer = customer
                return value
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found.")
        return value
    
    def create(self, validated_data):
        """Create building with facility and customer assignment."""
        facility_id = validated_data.pop('facility_id')
        customer_id = validated_data.pop('customer_id', None)
        
        building = Building(**validated_data)
        building.facility = self.facility
        
        if customer_id and hasattr(self, 'customer'):
            building.customer = self.customer
        
        building.save()
        return building


class UpdateBuildingSerializer(serializers.ModelSerializer):
    """
    Serializer for updating building information.
    """
    facility_id = serializers.UUIDField(required=False, allow_null=False)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Building
        fields = [
            'facility_id', 'name', 'building_type', 'description',
            'floor_count', 'square_footage', 'construction_year', 'address',
            'contact_name', 'contact_email', 'contact_phone', 'operational_status',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_facility_id(self, value):
        """
        Validate facility exists and is operational.
        """
        if value:
            try:
                facility = Facility.objects.get(pk=value)
                if not facility.is_operational:
                    raise serializers.ValidationError("Facility must be operational.")
                self.facility = facility
                return value
            except Facility.DoesNotExist:
                raise serializers.ValidationError("Facility not found.")
        return value
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            try:
                customer = Customer.objects.get(pk=value)
                if not customer.is_active:
                    raise serializers.ValidationError("Customer must be active.")
                self.customer = customer
                return value
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found.")
        return value
    
    def update(self, instance, validated_data):
        """Update building with facility and customer assignment."""
        facility_id = validated_data.pop('facility_id', None)
        customer_id = validated_data.pop('customer_id', None)
        
        # Update facility if provided
        if facility_id is not None and hasattr(self, 'facility'):
            instance.facility = self.facility
        
        # Update customer if provided
        if customer_id is not None:
            if customer_id and hasattr(self, 'customer'):
                instance.customer = self.customer
            else:
                instance.customer = None
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class BuildingListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for building list views.
    """
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    equipment_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Building
        fields = [
            'id', 'name', 'code', 'building_type', 'facility_name',
            'operational_status', 'customer_name', 'equipment_count', 'created_at'
        ]




# Location Serializers

class LocationSerializer(serializers.ModelSerializer):
    """
    Serializer for Location model with all fields.
    """
    entity_type = serializers.CharField(source='content_type.model', read_only=True)
    entity_id = serializers.UUIDField(source='object_id', read_only=True)
    has_coordinates = serializers.ReadOnlyField()
    full_location = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Location
        fields = [
            'id', 'entity_type', 'entity_id', 'name', 'description',
            'latitude', 'longitude', 'address', 'floor', 'room', 'zone',
            'additional_info', 'has_coordinates', 'full_location',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class CreateLocationSerializer(serializers.Serializer):
    """
    Serializer for creating a new location.
    """
    entity_type = serializers.CharField(required=True)
    entity_id = serializers.UUIDField(required=True)
    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    floor = serializers.CharField(max_length=50, required=False, allow_blank=True)
    room = serializers.CharField(max_length=50, required=False, allow_blank=True)
    zone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    additional_info = serializers.JSONField(required=False)
    
    def validate_latitude(self, value):
        """Validate latitude range."""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value
    
    def validate_longitude(self, value):
        """Validate longitude range."""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value
    
    def validate(self, data):
        """
        Validate entity exists.
        """
        from django.contrib.contenttypes.models import ContentType
        from django.apps import apps
        
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        
        # Get content type
        try:
            content_type = ContentType.objects.get(model=entity_type.lower())
            model_class = content_type.model_class()
            
            # Check if entity exists
            if not model_class.objects.filter(pk=entity_id).exists():
                raise serializers.ValidationError({
                    'entity_id': f'{entity_type} with this ID does not exist.'
                })
            
            # Check if location already exists for this entity
            if Location.objects.filter(content_type=content_type, object_id=entity_id).exists():
                raise serializers.ValidationError({
                    'entity_id': f'A location already exists for this {entity_type}.'
                })
            
            self.content_type = content_type
        except ContentType.DoesNotExist:
            raise serializers.ValidationError({
                'entity_type': f'Invalid entity type: {entity_type}'
            })
        
        return data
    
    def create(self, validated_data):
        """Create location with polymorphic relationship."""
        entity_type = validated_data.pop('entity_type')
        entity_id = validated_data.pop('entity_id')
        
        location = Location(
            content_type=self.content_type,
            object_id=entity_id,
            **validated_data
        )
        location.save()
        return location


class UpdateLocationSerializer(serializers.ModelSerializer):
    """
    Serializer for updating location information.
    """
    class Meta:
        model = Location
        fields = [
            'name', 'description', 'latitude', 'longitude', 'address',
            'floor', 'room', 'zone', 'additional_info'
        ]
    
    def validate_latitude(self, value):
        """Validate latitude range."""
        if value is not None and not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value
    
    def validate_longitude(self, value):
        """Validate longitude range."""
        if value is not None and not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value

