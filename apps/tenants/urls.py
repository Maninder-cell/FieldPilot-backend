"""
Tenant URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views
from .views_profile import (
    current_user_profile,
    user_tenant_memberships,
    update_tenant_profile
)

urlpatterns = [
    # Tenant management
    path('create/', views.create_tenant, name='create_tenant'),
    path('current/', views.current_tenant, name='current_tenant'),
    path('update/', views.update_tenant, name='update_tenant'),
    
    # Onboarding
    path('step/', views.complete_onboarding_step, name='complete_onboarding_step'),
    path('settings/', views.tenant_settings, name='tenant_settings'),
    
    # Members
    path('members/', views.tenant_members, name='tenant_members'),
    path('members/invite/', views.invite_member, name='invite_member'),
    path('members/<uuid:member_id>/role/', views.update_member_role, name='update_member_role'),
    path('members/<uuid:member_id>/remove/', views.remove_member, name='remove_member'),
    
    # Invitations
    path('invitations/pending/', views.pending_invitations, name='pending_invitations'),
    path('invitations/check/', views.check_invitation, name='check_invitation'),
    path('invitations/<str:token>/', views.get_invitation_by_token, name='get_invitation_by_token'),
    path('invitations/accept/<str:token>/', views.accept_invitation_by_token, name='accept_invitation_by_token'),
    path('invitations/<uuid:invitation_id>/resend/', views.resend_invitation, name='resend_invitation'),
    path('invitations/<uuid:invitation_id>/revoke/', views.revoke_invitation, name='revoke_invitation'),
    
    # User Profile (tenant-specific)
    path('profile/', current_user_profile, name='current_user_profile'),
    path('profile/memberships/', user_tenant_memberships, name='user_tenant_memberships'),
    path('profile/update/', update_tenant_profile, name='update_tenant_profile'),
    
    # Technician Wage Rates (Phase 2)
    path('technicians/wage-rates/', views.get_technician_wage_rates, name='get_technician_wage_rates'),
    path('technicians/wage-rates/create/', views.create_technician_wage_rate, name='create_technician_wage_rate'),
    path('technicians/wage-rates/<uuid:rate_id>/', views.get_technician_wage_rate, name='get_technician_wage_rate'),
    path('technicians/wage-rates/<uuid:rate_id>/update/', views.update_technician_wage_rate, name='update_technician_wage_rate'),
    path('technicians/wage-rates/<uuid:rate_id>/delete/', views.delete_technician_wage_rate, name='delete_technician_wage_rate'),
    path('technicians/<uuid:technician_id>/wage-rates/history/', views.get_technician_wage_rate_history, name='get_technician_wage_rate_history'),
]
