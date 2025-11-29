"""
Authentication URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token_refresh'),
    
    # Email verification
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    
    # Password management (3-step flow)
    path('forgot-password/', views.forgot_password, name='forgot_password'),  # Step 1: Send OTP
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),  # Step 2: Verify OTP
    path('reset-password/', views.reset_password, name='reset_password'),  # Step 3: Set new password
    path('change-password/', views.change_password, name='change_password'),
    
    # User profile
    path('me/', views.me, name='me'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/avatar/', views.upload_avatar, name='upload_avatar'),
]