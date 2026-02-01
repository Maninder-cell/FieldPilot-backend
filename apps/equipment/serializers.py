"""
Equipment Serializers

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from .models import Equipment
from apps.facilities.serializers import BuildingSerializer, CustomerSerializer, CustomerMinimalSerializer


class EquipmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Equipment model with nested building, facility, and customer data.
    """
    building = BuildingSerializer(read_only=True)
    building_id = serializers.UUIDField(write_only=True)
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    is_operational = serializers.ReadOnlyField()
    is_under_warranty = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Equipment
        fields = [
            'id', 'building', 'building_id', 'facility_name', 'equipment_number',
            'name', 'equipment_type', 'manufacturer', 'model', 'serial_number', 'description',
            'purchase_date', 'purchase_price', 'warranty_expiration', 'installation_date',
            'operational_status', 'condition', 'specifications',
            'customer', 'customer_id', 'notes', 'custom_fields',
            'is_operational', 'is_under_warranty',
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'equipment_number', 'created_by', 'created_at', 'updated_at']


class CreateEquipmentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new equipment.
    """
    building_id = serializers.UUIDField(required=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Equipment
        fields = [
            'building_id', 'name', 'equipment_type', 'manufacturer', 'model', 'serial_number', 'description',
            'purchase_date', 'purchase_price', 'warranty_expiration', 'installation_date',
            'operational_status', 'condition', 'specifications',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_building_id(self, value):
        """
        Validate building exists and is operational.
        """
        from apps.facilities.models import Building
        try:
            building = Building.objects.get(pk=value)
            if not building.is_operational:
                raise serializers.ValidationError("Building must be operational.")
            self.building = building
            return value
        except Building.DoesNotExist:
            raise serializers.ValidationError("Building not found.")
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            from apps.facilities.models import Customer
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
        """Create equipment with building and customer assignment."""
        building_id = validated_data.pop('building_id')
        customer_id = validated_data.pop('customer_id', None)
        
        equipment = Equipment(**validated_data)
        equipment.building = self.building
        
        if customer_id and hasattr(self, 'customer'):
            equipment.customer = self.customer
        
        equipment.save()
        return equipment


class UpdateEquipmentSerializer(serializers.ModelSerializer):
    """
    Serializer for updating equipment information.
    """
    building_id = serializers.UUIDField(required=False, allow_null=False)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Equipment
        fields = [
            'building_id', 'name', 'equipment_type', 'manufacturer', 'model', 'serial_number', 'description',
            'purchase_date', 'purchase_price', 'warranty_expiration', 'installation_date',
            'operational_status', 'condition', 'specifications',
            'customer_id', 'notes', 'custom_fields'
        ]
    
    def validate_building_id(self, value):
        """
        Validate building exists and is operational.
        """
        if value:
            from apps.facilities.models import Building
            try:
                building = Building.objects.get(pk=value)
                if not building.is_operational:
                    raise serializers.ValidationError("Building must be operational.")
                self.building = building
                return value
            except Building.DoesNotExist:
                raise serializers.ValidationError("Building not found.")
        return value
    
    def validate_customer_id(self, value):
        """
        Validate customer exists and is active.
        """
        if value:
            from apps.facilities.models import Customer
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
        """Update equipment with building and customer assignment."""
        building_id = validated_data.pop('building_id', None)
        customer_id = validated_data.pop('customer_id', None)
        
        # Update building if provided
        if building_id is not None and hasattr(self, 'building'):
            instance.building = self.building
        
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


class EquipmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for equipment list views.
    """
    building_name = serializers.CharField(source='building.name', read_only=True)
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer = CustomerMinimalSerializer(read_only=True)
    
    class Meta:
        model = Equipment
        fields = [
            'id', 'equipment_number', 'name', 'equipment_type', 'manufacturer', 'model',
            'building_name', 'facility_name', 'operational_status', 'condition',
            'customer_name', 'customer', 'created_at'
        ]
