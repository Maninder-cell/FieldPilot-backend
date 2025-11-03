"""
Custom JWT Authentication for Multi-Tenant Setup

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_tenants.utils import schema_context


class TenantJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that looks up users in the public schema.
    
    In a multi-tenant setup with schema-per-tenant, users are stored in the
    public schema (shared), but JWT authentication runs in the tenant schema context.
    This class ensures user lookup happens in the public schema.
    """
    
    def get_user(self, validated_token):
        """
        Override to look up user in public schema.
        """
        try:
            user_id = validated_token[self.get_jwt_value(validated_token)]
        except KeyError:
            from rest_framework_simplejwt.exceptions import InvalidToken
            raise InvalidToken("Token contained no recognizable user identification")
        
        # Look up user in public schema
        with schema_context('public'):
            try:
                from .models import User
                user = User.objects.get(**{self.user_model.USERNAME_FIELD: user_id})
            except User.DoesNotExist:
                from rest_framework_simplejwt.exceptions import AuthenticationFailed
                raise AuthenticationFailed("User not found", code="user_not_found")
        
        if not user.is_active:
            from rest_framework_simplejwt.exceptions import AuthenticationFailed
            raise AuthenticationFailed("User is inactive", code="user_inactive")
        
        return user
    
    def get_jwt_value(self, validated_token):
        """
        Get the user identifier from the token.
        """
        return 'user_id'
