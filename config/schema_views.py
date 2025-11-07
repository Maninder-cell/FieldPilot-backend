"""
Custom Schema Views for Multi-Tenant API Documentation

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""

from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.generators import SchemaGenerator
from django.db import connection
from django_tenants.utils import get_public_schema_name


class PublicSchemaView(SpectacularAPIView):
    """
    Schema view that only includes PUBLIC schema endpoints.
    Filters out tenant-specific APIs.
    """
    
    def get(self, request, *args, **kwargs):
        # Force public schema context
        connection.set_schema_to_public()
        
        # Get the full schema
        generator = self.generator_class(patterns=self.patterns, urlconf=self.urlconf)
        schema = generator.get_schema(request=request, public=self.serve_public)
        
        # Filter to only include public endpoints
        public_prefixes = (
            '/api/v1/auth/',
            '/api/v1/onboarding/',
            '/api/v1/billing/',
            '/health/',
        )
        
        # Filter paths
        filtered_paths = {}
        for path, path_item in schema.get('paths', {}).items():
            if any(path.startswith(prefix) for prefix in public_prefixes):
                filtered_paths[path] = path_item
        
        schema['paths'] = filtered_paths
        
        # Filter tags to only include those used in filtered paths
        used_tags = set()
        for path_item in filtered_paths.values():
            for method_data in path_item.values():
                if isinstance(method_data, dict) and 'tags' in method_data:
                    used_tags.update(method_data['tags'])
        
        # Define public tag descriptions
        public_tag_descriptions = {
            'Authentication': 'User registration, login, profile management, and password operations',
            'Onboarding': 'Company/tenant creation, team member management, and onboarding flow',
            'Billing': 'Subscription plans, payment methods, invoices, and billing management',
            'Health': 'System health monitoring and status checks',
        }
        
        # Create or update tags list
        if 'tags' in schema:
            # Filter to keep only used tags
            existing_tags = {tag.get('name'): tag for tag in schema.get('tags', [])}
            schema['tags'] = []
            
            for tag_name in sorted(used_tags):
                # Use existing tag if available, otherwise create new
                if tag_name in existing_tags:
                    tag_entry = existing_tags[tag_name]
                else:
                    tag_entry = {'name': tag_name}
                
                # Set description
                if tag_name in public_tag_descriptions:
                    tag_entry['description'] = public_tag_descriptions[tag_name]
                
                schema['tags'].append(tag_entry)
        else:
            # Create tags from scratch
            schema['tags'] = []
            for tag_name in sorted(used_tags):
                tag_entry = {'name': tag_name}
                if tag_name in public_tag_descriptions:
                    tag_entry['description'] = public_tag_descriptions[tag_name]
                schema['tags'].append(tag_entry)
        
        # Return the filtered schema
        from rest_framework.response import Response
        return Response(schema)


class TenantSchemaView(SpectacularAPIView):
    """
    Schema view that only includes TENANT schema endpoints.
    Filters out public-only APIs.
    """
    
    def get(self, request, *args, **kwargs):
        # Check if we're on public schema
        if connection.schema_name == get_public_schema_name():
            # Allow viewing tenant docs from public domain for development
            pass
        
        # Get the full schema
        generator = self.generator_class(patterns=self.patterns, urlconf=self.urlconf)
        schema = generator.get_schema(request=request, public=self.serve_public)
        
        # Filter to exclude public endpoints
        public_prefixes = (
            '/api/v1/auth/',
            '/api/v1/onboarding/',
            '/api/v1/billing/',
            '/health/',
            '/admin/',
            '/api/schema/',
            '/api/docs/',
            '/api/redoc/',
        )
        
        # Filter paths - exclude public endpoints
        filtered_paths = {}
        for path, path_item in schema.get('paths', {}).items():
            if not any(path.startswith(prefix) for prefix in public_prefixes):
                filtered_paths[path] = path_item
        
        schema['paths'] = filtered_paths
        
        # Filter tags to only include those used in filtered paths
        used_tags = set()
        for path_item in filtered_paths.values():
            for method_data in path_item.values():
                if isinstance(method_data, dict) and 'tags' in method_data:
                    used_tags.update(method_data['tags'])
        
        # Define tenant tag descriptions
        tenant_tag_descriptions = {
            'Customers': '👥 Customer management, invitations, and customer assets',
            'Facilities': '🏢 Facility management, buildings, and equipment tracking',
            'Buildings': '🏗️ Building management and operations within facilities',
            'Locations': '📍 Location management with coordinates and address details',
            'Equipment': '⚙️ Equipment tracking, history, and maintenance records',
        }
        
        # Create tags list from used_tags (don't rely on existing tags from settings)
        schema['tags'] = []
        for tag_name in sorted(used_tags):
            tag_entry = {'name': tag_name}
            if tag_name in tenant_tag_descriptions:
                tag_entry['description'] = tenant_tag_descriptions[tag_name]
            schema['tags'].append(tag_entry)
        
        # Return the filtered schema
        return self._get_response_for_schema(schema)
    
    def _get_response_for_schema(self, schema):
        """Helper to return response with schema"""
        from rest_framework.response import Response
        return Response(schema)
