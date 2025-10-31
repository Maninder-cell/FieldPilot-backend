"""
Authentication Views

Copyright (c) 2025 FieldPilot. All rights reserved.
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
    PasswordResetConfirmSerializer, EmailVerificationSerializer,
    ResendOTPSerializer, ChangePasswordSerializer, UserSerializer,
    UserProfileSerializer, UpdateProfileSerializer
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import IsAdminUser

logger = logging.getLogger(__name__)


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
    """Send OTP email to user."""
    try:
        subject_map = {
            'email_verification': 'Verify Your Email - FieldPilot',
            'password_reset': 'Password Reset Code - FieldPilot'
        }
        
        message_map = {
            'email_verification': f'Your email verification code is: {user.otp_code}. This code expires in 10 minutes.',
            'password_reset': f'Your password reset code is: {user.otp_code}. This code expires in 10 minutes.'
        }
        
        send_mail(
            subject=subject_map.get(purpose, 'OTP Code - FieldPilot'),
            message=message_map.get(purpose, f'Your OTP code is: {user.otp_code}'),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
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
def register(request):
    """
    Register a new user within current tenant.
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
            
            # Create user profile
            UserProfile.objects.create(user=user)
            
            # Send verification email
            if send_otp_email(user, 'email_verification'):
                logger.info(f"User registered: {user.email}")
                
                return success_response(
                    data={
                        'user': UserSerializer(user).data,
                        'message': 'Registration successful. Please check your email for verification code.'
                    },
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return error_response(
                    message="Registration successful but failed to send verification email. Please try resending OTP.",
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
def login(request):
    """
    User login with JWT token generation.
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
        
        logger.info(f"User logged in: {user.email}")
        
        return success_response(
            data={
                'user': UserSerializer(user).data,
                'tokens': tokens,
                'token_type': 'Bearer',
                'expires_in': 900  # 15 minutes for access token
            },
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
def logout(request):
    """
    User logout (blacklist refresh token).
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
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
def verify_email(request):
    """
    Verify email with OTP code.
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
def resend_otp(request):
    """
    Resend OTP for email verification or password reset.
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
def forgot_password(request):
    """
    Request password reset OTP.
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
    summary='Reset password',
    description='Reset password using OTP verification',
    request=PasswordResetConfirmSerializer,
    responses={
        200: {'description': 'Password reset successful'},
        400: {'description': 'Invalid OTP or passwords'},
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password with OTP verification.
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
def change_password(request):
    """
    Change password for authenticated user.
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
def profile(request):
    """
    Get user profile information.
    """
    try:
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        serializer = UserProfileSerializer(profile)
        
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
def update_profile(request):
    """
    Update user profile information.
    """
    try:
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        serializer = UpdateProfileSerializer(profile, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid profile data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        # Return updated profile
        updated_profile = UserProfileSerializer(profile).data
        
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
    summary='Get current user info',
    description='Retrieve information about the currently authenticated user',
    responses={
        200: UserSerializer,
        401: {'description': 'Authentication required'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Get current user information.
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