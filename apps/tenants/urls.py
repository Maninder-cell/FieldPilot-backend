"""
Tenant URLs

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Tenant management
    path('create/', views.create_tenant, name='create_tenant'),
    path('current/', views.current_tenant, name='current_tenant'),
    path('update/', views.update_tenant, name='update_tenant'),
    
    # Onboarding
    path('onboarding/step/', views.complete_onboarding_step, name='complete_onboarding_step'),
    
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
]
