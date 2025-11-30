"""
Authentication Models

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for FieldRino.
    For multi-tenant role management, use TenantMember model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    
    # Personal information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    avatar_url = models.URLField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Verification
    email_verified_at = models.DateTimeField(null=True, blank=True)
    verification_token = models.CharField(max_length=255, blank=True)
    
    # Two-factor authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=255, blank=True)
    
    # Password reset
    password_reset_token = models.CharField(max_length=255, blank=True)
    password_reset_expires = models.DateTimeField(null=True, blank=True)
    
    # OTP for various purposes
    otp_code = models.CharField(max_length=6, blank=True)
    otp_expires = models.DateTimeField(null=True, blank=True)
    otp_purpose = models.CharField(
        max_length=50,
        choices=[
            ('email_verification', 'Email Verification'),
            ('password_reset', 'Password Reset'),
            ('two_factor', 'Two Factor Authentication'),
        ],
        blank=True
    )
    
    # Timestamps
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
        ]
        # Fix reverse accessor conflicts
        default_related_name = 'fieldrino_users'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()
    

    
    def set_otp(self, purpose, length=6):
        """Generate and set OTP for specific purpose."""
        import random
        import string
        
        self.otp_code = ''.join(random.choices(string.digits, k=length))
        self.otp_expires = timezone.now() + timezone.timedelta(minutes=10)  # 10 minutes
        self.otp_purpose = purpose
        self.save()
        
        return self.otp_code
    
    def verify_otp(self, code, purpose):
        """Verify OTP code."""
        if (self.otp_code == code and 
            self.otp_purpose == purpose and 
            self.otp_expires and 
            timezone.now() < self.otp_expires):
            
            # Clear OTP after successful verification
            self.otp_code = ''
            self.otp_expires = None
            self.otp_purpose = ''
            
            if purpose == 'email_verification':
                self.is_verified = True
                self.email_verified_at = timezone.now()
            
            self.save()
            return True
        
        return False
    



class UserProfile(models.Model):
    """
    Extended user profile information.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Additional personal information
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True)
    
    # Work information
    hire_date = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='direct_reports'
    )
    
    # Skills and certifications
    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    
    # Preferences
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.full_name}"


class LoginAttempt(models.Model):
    """
    Track login attempts for security monitoring.
    """
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]
    
    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{status} login attempt for {self.email} at {self.created_at}"