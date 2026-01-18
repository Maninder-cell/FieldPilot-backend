"""
Authentication Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
import logging

from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer, LoginSerializer, PasswordResetRequestSerializer,
    PasswordResetVerifyOTPSerializer, PasswordResetConfirmSerializer, EmailVerificationSerializer,
    ResendOTPSerializer, ChangePasswordSerializer, UserSerializer,
    UserProfileSerializer, UpdateProfileSerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import IsAdminUser
from functools import wraps

logger = logging.getLogger(__name__)


def public_schema_only(view_func):
    """
    Decorator to restrict view access to public schema only.
    Used for registration and other onboarding endpoints.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.db import connection
        
        current_schema = connection.schema_name
        if current_schema != 'public':
            return error_response(
                message="This endpoint is only available from the onboarding portal. Please access via http://localhost:8000",
                status_code=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


class TokenRefreshView(BaseTokenRefreshView):
    """
    Custom Token Refresh View with proper Swagger documentation.
    """
    @extend_schema(
        tags=['Authentication'],
        summary='Refresh access token',
        description='Get a new access token using a valid refresh token',
        request={
            'type': 'object',
            'properties': {
                'refresh': {
                    'type': 'string',
                    'description': 'Valid refresh token'
                }
            },
            'required': ['refresh']
        },
        responses={
            200: {
                'description': 'Token refreshed successfully',
                'type': 'object',
                'properties': {
                    'access': {'type': 'string', 'description': 'New access token'},
                    'refresh': {'type': 'string', 'description': 'New refresh token (if rotation enabled)'}
                }
            },
            401: {'description': 'Invalid or expired refresh token'},
        },
        examples=[
            OpenApiExample(
                'Token Refresh',
                value={'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'},
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


def get_tokens_for_user(user):
    """Generate JWT tokens for user."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_otp_email(user, purpose):
    """Send OTP email to user using professional templates."""
    from apps.core.email_utils import send_otp_email as send_template_otp
    try:
        return send_template_otp(user, purpose)
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False


@extend_schema(
    tags=['Authentication'],
    summary='Register new user',
    description='Register a new user account with email verification. An OTP will be sent to the provided email.',
    request=UserRegistrationSerializer,
    responses={
        201: UserSerializer,
        400: {'description': 'Invalid registration data'},
    },
    examples=[
        OpenApiExample(
            'User Registration',
            value={
                'email': 'user@example.com',
                'password': 'SecurePass123!',
                'password_confirm': 'SecurePass123!',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+1234567890',
                'role': 'employee'
            },
            request_only=True
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def register(request):
    """
    Register a new user.
    
    Note: Registration is only available from the public schema (localhost).
    Users are global and not tied to specific tenants.
    """
    serializer = UserRegistrationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid registration data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            user = serializer.save()
            
            # Create user profile if it doesn't exist
            UserProfile.objects.get_or_create(user=user)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Send verification email
            if send_otp_email(user, 'email_verification'):
                logger.info(f"User registered: {user.email}")
                
                return success_response(
                    data={
                        'user': UserSerializer(user).data,
                        'access': access_token,
                        'refresh': refresh_token,
                        'message': 'Registration successful. Please check your email for verification code.'
                    },
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return success_response(
                    data={
                        'user': UserSerializer(user).data,
                        'access': access_token,
                        'refresh': refresh_token,
                        'message': 'Registration successful but failed to send verification email. Please try resending OTP.'
                    },
                    status_code=status.HTTP_201_CREATED
                )
                
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        return error_response(
            message="Registration failed. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='User login',
    description='Authenticate user and return JWT access and refresh tokens',
    request=LoginSerializer,
    responses={
        200: {'description': 'Login successful', 'type': 'object'},
        400: {'description': 'Invalid credentials'},
    },
    examples=[
        OpenApiExample(
            'User Login',
            value={
                'email': 'user@example.com',
                'password': 'SecurePass123!',
                'remember_me': False
            },
            request_only=True
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def login(request):
    """
    User login with JWT token generation.
    
    Note: Login is only available from the public schema (localhost).
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid login credentials",
            details=serializer.errors,
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        user = serializer.validated_data['user']
        
        # Check if email is verified
        if not user.is_verified:
            return error_response(
                message="Please verify your email before logging in.",
                code="EMAIL_NOT_VERIFIED",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Generate tokens
        tokens = get_tokens_for_user(user)
        
        # Get tenant membership information
        from apps.tenants.models import TenantMember
        from django.db import connection
        tenant_membership = None
        tenant_data = None
        
        try:
            # Get the user's tenant membership (assuming user has one active membership)
            membership = TenantMember.objects.filter(
                user=user,
                is_active=True
            ).select_related('tenant').first()
            
            if membership:
                tenant_membership = {
                    'role': membership.role,
                    'employee_id': membership.employee_id,
                    'department': membership.department,
                    'job_title': membership.job_title,
                }
                tenant_data = {
                    'id': str(membership.tenant.id),
                    'name': membership.tenant.name,
                    'slug': membership.tenant.slug,
                }
            else:
                # Check if user is a customer (customers don't have TenantMember records)
                # We need to find which tenant schema has this customer
                from apps.tenants.models import Tenant
                from django_tenants.utils import schema_context
                
                logger.info(f"Checking customer profile for user: {user.email}")
                
                for tenant in Tenant.objects.all():
                    try:
                        logger.info(f"Checking tenant: {tenant.slug}")
                        with schema_context(tenant.schema_name):
                            from apps.facilities.models import Customer
                            customer = Customer.objects.filter(user=user).first()
                            if customer:
                                # Found the customer's tenant
                                logger.info(f"Found customer in tenant: {tenant.slug}")
                                tenant_data = {
                                    'id': str(tenant.id),
                                    'name': tenant.name,
                                    'slug': tenant.slug,
                                }
                                tenant_membership = {
                                    'role': 'customer',
                                    'employee_id': '',
                                    'department': '',
                                    'job_title': 'Customer',
                                }
                                break
                    except Exception as ex:
                        logger.warning(f"Error checking tenant {tenant.slug}: {str(ex)}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Could not fetch tenant membership for {user.email}: {str(e)}")
        
        # Update last login
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        logger.info(f"User logged in: {user.email}")
        
        # Pass membership as context to UserSerializer
        serializer_context = {}
        if membership:
            serializer_context['membership'] = membership
        
        response_data = {
            'user': UserSerializer(user, context=serializer_context).data,
            'tokens': tokens,
            'token_type': 'Bearer',
            'expires_in': 900  # 15 minutes for access token
        }
        
        # Add tenant information if available
        if tenant_membership:
            response_data['tenant_membership'] = tenant_membership
        if tenant_data:
            response_data['tenant'] = tenant_data
        
        return success_response(
            data=response_data,
            message="Login successful"
        )
        
    except Exception as e:
        logger.error(f"Login failed: {str(e)}", exc_info=True)
        return error_response(
            message="Login failed. Please try again.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@extend_schema(
    tags=['Authentication'],
    summary='User logout',
    description='Logout user and blacklist refresh token',
    request={'type': 'object', 'properties': {'refresh_token': {'type': 'string'}}},
    responses={
        200: {'description': 'Logout successful'},
        400: {'description': 'Invalid refresh token'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def logout(request):
    """
    User logout (blacklist refresh token).
    
    Note: Logout is only available from the public schema (localhost).
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                # Try to blacklist if the extension is installed
                if hasattr(token, 'blacklist'):
                    token.blacklist()
                else:
                    # If blacklist not available, just validate the token
                    # The token will expire naturally
                    token.check_blacklist()
            except AttributeError:
                # Blacklist not installed, token will expire naturally
                pass
            except Exception as token_error:
                logger.warning(f"Token blacklist error: {str(token_error)}")
        
        logger.info(f"User logged out: {request.user.email}")
        
        return success_response(
            message="Logout successful"
        )
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return error_response(
            message="Logout failed",
            status_code=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    tags=['Authentication'],
    summary='Verify email',
    description='Verify user email address with OTP code',
    request=EmailVerificationSerializer,
    responses={
        200: {'description': 'Email verified successfully'},
        400: {'description': 'Invalid or expired OTP'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def verify_email(request):
    """
    Verify email with OTP code.
    
    Note: Email verification is only available from the public schema (localhost).
    """
    serializer = EmailVerificationSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid verification data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = serializer.validated_data['user']
        
        logger.info(f"Email verified: {user.email}")
        
        return success_response(
            data={
                'user': UserSerializer(user).data
            },
            message="Email verified successfully"
        )
        
    except Exception as e:
        logger.error(f"Email verification failed: {str(e)}")
        return error_response(
            message="Email verification failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Resend OTP',
    description='Resend OTP code for email verification or password reset',
    request=ResendOTPSerializer,
    responses={
        200: {'description': 'OTP sent successfully'},
        400: {'description': 'Invalid request'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def resend_otp(request):
    """
    Resend OTP for email verification or password reset.
    
    Note: OTP resend is only available from the public schema (localhost).
    """
    serializer = ResendOTPSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid request data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = serializer.validated_data.get('user')
        purpose = serializer.validated_data['purpose']
        
        if user:
            # Generate new OTP
            user.set_otp(purpose)
            
            # Send OTP email
            if send_otp_email(user, purpose):
                return success_response(
                    message="OTP sent successfully. Please check your email."
                )
            else:
                return error_response(
                    message="Failed to send OTP. Please try again.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Don't reveal if email exists, but return success for security
            return success_response(
                message="If the email exists, OTP has been sent."
            )
            
    except Exception as e:
        logger.error(f"Resend OTP failed: {str(e)}")
        return error_response(
            message="Failed to resend OTP",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Forgot password',
    description='Request password reset OTP to be sent to email',
    request=PasswordResetRequestSerializer,
    responses={
        200: {'description': 'Password reset OTP sent'},
        400: {'description': 'Invalid email'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def forgot_password(request):
    """
    Request password reset OTP.
    
    Note: Password reset is only available from the public schema (localhost).
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid email",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = getattr(serializer, 'user', None)
        
        if user:
            # Generate OTP for password reset
            user.set_otp('password_reset')
            
            # Send OTP email
            if send_otp_email(user, 'password_reset'):
                logger.info(f"Password reset OTP sent: {user.email}")
            
        # Always return success for security (don't reveal if email exists)
        return success_response(
            message="If the email exists, a password reset code has been sent."
        )
        
    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        return error_response(
            message="Failed to process password reset request",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Verify reset OTP',
    description='Verify OTP code for password reset (Step 2 of 3). Returns a reset token.',
    request=PasswordResetVerifyOTPSerializer,
    responses={
        200: {'description': 'OTP verified successfully, reset token returned'},
        400: {'description': 'Invalid OTP'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def verify_reset_otp(request):
    """
    Verify OTP for password reset (Step 2).
    
    Flow:
    1. Call forgot-password to get OTP
    2. Call verify-reset-otp to verify OTP (this endpoint) - returns reset_token
    3. Call reset-password with reset_token to set new password
    
    Note: Password reset is only available from the public schema (localhost).
    """
    serializer = PasswordResetVerifyOTPSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid OTP",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = serializer.validated_data['user']
        
        # Generate a secure reset token
        import secrets
        reset_token = secrets.token_urlsafe(32)
        
        # Save reset token with 15 minute expiry
        user.password_reset_token = reset_token
        user.password_reset_expires = timezone.now() + timezone.timedelta(minutes=15)
        user.save()
        
        logger.info(f"Password reset OTP verified: {user.email}")
        
        return success_response(
            message="OTP verified successfully. Use the reset token to set your new password.",
            data={
                'email': user.email,
                'reset_token': reset_token,
                'expires_in': '15 minutes'
            }
        )
        
    except Exception as e:
        logger.error(f"OTP verification failed: {str(e)}")
        return error_response(
            message="OTP verification failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Reset password',
    description='Reset password using reset token (Step 3 of 3). No OTP required.',
    request=PasswordResetConfirmSerializer,
    responses={
        200: {'description': 'Password reset successful'},
        400: {'description': 'Invalid reset token or passwords'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@public_schema_only
def reset_password(request):
    """
    Reset password with reset token (Step 3).
    
    Flow:
    1. Call forgot-password to get OTP
    2. Call verify-reset-otp to verify OTP and get reset_token
    3. Call reset-password with reset_token to set new password (this endpoint)
    
    Note: Password reset is only available from the public schema (localhost).
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid reset data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = serializer.validated_data['user']
        new_password = serializer.validated_data['new_password']
        
        # Set new password
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        
        # Clear reset token after use
        user.password_reset_token = ''
        user.password_reset_expires = None
        
        user.save()
        
        logger.info(f"Password reset successful: {user.email}")
        
        return success_response(
            message="Password reset successful. You can now login with your new password."
        )
        
    except Exception as e:
        logger.error(f"Password reset failed: {str(e)}")
        return error_response(
            message="Password reset failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Change password',
    description='Change password for authenticated user',
    request=ChangePasswordSerializer,
    responses={
        200: {'description': 'Password changed successfully'},
        400: {'description': 'Invalid current password or new passwords'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def change_password(request):
    """
    Change password for authenticated user.
    
    Note: Password change is only available from the public schema (localhost).
    """
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid password data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = request.user
        new_password = serializer.validated_data['new_password']
        
        # Set new password
        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.save()
        
        logger.info(f"Password changed: {user.email}")
        
        return success_response(
            message="Password changed successfully"
        )
        
    except Exception as e:
        logger.error(f"Password change failed: {str(e)}")
        return error_response(
            message="Password change failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Get user profile',
    description='Get detailed user profile information',
    responses={
        200: UserProfileSerializer,
        401: {'description': 'Authentication required'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def profile(request):
    """
    Get user profile information.
    
    Note: Profile access is only available from the public schema (localhost).
    """
    try:
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        serializer = UserProfileSerializer(profile, context={'request': request})
        
        return success_response(
            data=serializer.data,
            message="Profile retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Profile retrieval failed: {str(e)}")
        return error_response(
            message="Failed to retrieve profile",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Update user profile',
    description='Update user profile information',
    request=UpdateProfileSerializer,
    responses={
        200: UserProfileSerializer,
        400: {'description': 'Invalid profile data'},
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@public_schema_only
def update_profile(request):
    """
    Update user profile information.
    
    Note: Profile update is only available from the public schema (localhost).
    """
    try:
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        serializer = UpdateProfileSerializer(
            profile, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid profile data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        # Return updated profile with request context
        updated_profile = UserProfileSerializer(profile, context={'request': request}).data
        
        logger.info(f"Profile updated: {user.email}")
        
        return success_response(
            data=updated_profile,
            message="Profile updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Profile update failed: {str(e)}")
        return error_response(
            message="Profile update failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Upload user avatar',
    description='Upload avatar image for the authenticated user',
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'avatar': {
                    'type': 'string',
                    'format': 'binary'
                }
            }
        }
    },
    responses={
        200: {'description': 'Avatar uploaded successfully'},
        400: {'description': 'Invalid file or file too large'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def upload_avatar(request):
    """
    Upload user avatar image.
    
    Note: Avatar upload is only available from the public schema (localhost).
    """
    try:
        if 'avatar' not in request.FILES:
            return error_response(
                message="No avatar file provided",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        avatar_file = request.FILES['avatar']
        
        # Validate file size (max 5MB)
        if avatar_file.size > 5 * 1024 * 1024:
            return error_response(
                message="File size too large. Maximum size is 5MB",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if avatar_file.content_type not in allowed_types:
            return error_response(
                message="Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Save the file
        import os
        from django.conf import settings
        from django.core.files.storage import default_storage
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        import uuid
        file_extension = os.path.splitext(avatar_file.name)[1]
        filename = f"{request.user.id}_{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join('avatars', filename)
        
        # Save file
        saved_path = default_storage.save(file_path, avatar_file)
        
        # Generate URL
        avatar_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
        
        # Update user avatar_url
        request.user.avatar_url = avatar_url
        request.user.save()
        
        logger.info(f"Avatar uploaded for user: {request.user.email}")
        
        return success_response(
            data={'avatar_url': avatar_url},
            message="Avatar uploaded successfully"
        )
        
    except Exception as e:
        logger.error(f"Avatar upload failed: {str(e)}")
        return error_response(
            message="Failed to upload avatar",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Authentication'],
    summary='Get current user info',
    description='Retrieve information about the currently authenticated user',
    responses={
        200: UserSerializer,
        401: {'description': 'Authentication required'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def me(request):
    """
    Get current user information.
    
    Note: User info is only available from the public schema (localhost).
    """
    try:
        serializer = UserSerializer(request.user)
        
        return success_response(
            data=serializer.data,
            message="User information retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"User info retrieval failed: {str(e)}")
        return error_response(
            message="Failed to retrieve user information",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )