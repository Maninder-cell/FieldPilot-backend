"""
Facilities URLs

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

app_name = 'facilities'

urlpatterns = [
    # Customer endpoints
    path('customers/', views.customer_list_create, name='customer-list-create'),
    path('customers/<uuid:customer_id>/', views.customer_detail, name='customer-detail'),
    path('customers/invite/', views.customer_invite, name='customer-invite'),
    path('customers/<uuid:customer_id>/assets/', views.customer_assets, name='customer-assets'),
    path('customers/invitations/verify/', views.verify_customer_invitation, name='verify-customer-invitation'),
    path('customers/invitations/accept/', views.accept_customer_invitation, name='accept-customer-invitation'),
    
    # Facility endpoints
    path('facilities/', views.facility_list_create, name='facility-list-create'),
    path('facilities/<uuid:facility_id>/', views.facility_detail, name='facility-detail'),
    path('facilities/<uuid:facility_id>/buildings/', views.facility_buildings, name='facility-buildings'),
    path('facilities/<uuid:facility_id>/equipment/', views.facility_equipment, name='facility-equipment'),
    
    # Building endpoints
    path('buildings/', views.building_list_create, name='building-list-create'),
    path('buildings/<uuid:building_id>/', views.building_detail, name='building-detail'),
    path('buildings/<uuid:building_id>/equipment/', views.building_equipment, name='building-equipment'),
    
    # Location endpoints
    path('locations/', views.location_list_create, name='location-list-create'),
    path('locations/<uuid:location_id>/', views.location_detail, name='location-detail'),
]