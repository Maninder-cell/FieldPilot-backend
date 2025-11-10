"""
Authentication Serializers

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, UserProfile, LoginAttempt


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 'first_name', 
            'last_name', 'phone', 'role', 'department', 'job_title'
        ]
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs
    
    def validate_email(self, value):
        """Validate email is unique."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    
    def create(self, validated_data):
        """Create user with validated data."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        # Generate OTP for email verification
        user.set_otp('email_verification')
        
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Validate login credentials."""
        email = attrs.get('email', '').lower()
        password = attrs.get('password')
        
        if email and password:
            # Get request for IP tracking
            request = self.context.get('request')
            ip_address = self.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '') if request else ''
            
            # Authenticate user
            user = authenticate(
                request=request,
                username=email,
                password=password
            )
            
            # Log login attempt
            LoginAttempt.objects.create(
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=user is not None,
                failure_reason='' if user else 'Invalid credentials'
            )
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError("User account is disabled.")
                
                # Update last login
                user.last_login_at = timezone.now()
                user.save(update_fields=['last_login_at'])
                
                attrs['user'] = user
            else:
                raise serializers.ValidationError("Invalid email or password.")
        else:
            raise serializers.ValidationError("Must include email and password.")
        
        return attrs
    
    def get_client_ip(self, request):
        """Get client IP address."""
        if not request:
            return '127.0.0.1'
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email exists."""
        try:
            user = User.objects.get(email__iexact=value)
            self.user = user
            return value.lower()
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return value.lower()


class PasswordResetVerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP during password reset.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, attrs):
        """Validate OTP for password reset."""
        email = attrs['email'].lower()
        otp_code = attrs['otp_code']
        
        try:
            user = User.objects.get(email__iexact=email)
            if not user.verify_otp(otp_code, 'password_reset'):
                raise serializers.ValidationError("Invalid or expired OTP code.")
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP code.")
        
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation (after OTP verification).
    Uses reset token instead of OTP.
    """
    email = serializers.EmailField()
    reset_token = serializers.CharField(max_length=255)
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        """Validate reset token and password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        
        email = attrs['email'].lower()
        reset_token = attrs['reset_token']
        
        try:
            user = User.objects.get(email__iexact=email)
            
            # Verify reset token
            if not user.password_reset_token or user.password_reset_token != reset_token:
                raise serializers.ValidationError("Invalid or expired reset token.")
            
            # Check if token is expired (valid for 15 minutes)
            if not user.password_reset_expires or user.password_reset_expires < timezone.now():
                raise serializers.ValidationError("Reset token has expired. Please request a new one.")
            
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or reset token.")
        
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification with OTP.
    """
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, attrs):
        """Validate OTP for email verification."""
        email = attrs['email'].lower()
        otp_code = attrs['otp_code']
        
        try:
            user = User.objects.get(email__iexact=email)
            if user.is_verified:
                raise serializers.ValidationError("Email is already verified.")
            
            if not user.verify_otp(otp_code, 'email_verification'):
                raise serializers.ValidationError("Invalid or expired OTP code.")
            
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP code.")
        
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    """
    Serializer for resending OTP.
    """
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=['email_verification', 'password_reset']
    )
    
    def validate(self, attrs):
        """Validate email exists."""
        email = attrs['email'].lower()
        purpose = attrs['purpose']
        
        try:
            user = User.objects.get(email__iexact=email)
            
            if purpose == 'email_verification' and user.is_verified:
                raise serializers.ValidationError("Email is already verified.")
            
            attrs['user'] = user
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            pass
        
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password.
    """
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        """Validate current password and new password confirmation."""
        user = self.context['request'].user
        
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError("Current password is incorrect.")
        
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user information.
    """
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'avatar_url', 'role', 'employee_id', 'department',
            'job_title', 'is_active', 'is_verified', 'two_factor_enabled',
            'created_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'employee_id', 'is_verified', 'created_at', 'last_login_at'
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile.
    """
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'user', 'date_of_birth', 'address', 'city', 'state',
            'zip_code', 'country', 'emergency_contact_name',
            'emergency_contact_phone', 'emergency_contact_relationship',
            'hire_date', 'skills', 'certifications', 'timezone',
            'language', 'email_notifications', 'sms_notifications',
            'push_notifications'
        ]


class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile.
    """
    # User fields
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False)
    avatar_url = serializers.URLField(required=False)
    department = serializers.CharField(max_length=100, required=False)
    job_title = serializers.CharField(max_length=100, required=False)
    
    class Meta:
        model = UserProfile
        fields = [
            'first_name', 'last_name', 'phone', 'avatar_url',
            'department', 'job_title', 'date_of_birth', 'address',
            'city', 'state', 'zip_code', 'country',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship', 'skills', 'certifications',
            'timezone', 'language', 'email_notifications',
            'sms_notifications', 'push_notifications'
        ]
    
    def update(self, instance, validated_data):
        """Update both user and profile."""
        # Extract user fields
        user_fields = {
            'first_name', 'last_name', 'phone', 'avatar_url',
            'department', 'job_title'
        }
        
        user_data = {k: v for k, v in validated_data.items() if k in user_fields}
        profile_data = {k: v for k, v in validated_data.items() if k not in user_fields}
        
        # Update user
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        
        # Update profile
        if profile_data:
            for attr, value in profile_data.items():
                setattr(instance, attr, value)
            instance.save()
        
        return instance