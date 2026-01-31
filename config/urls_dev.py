"""
FieldRino Development URL Configuration

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularSwaggerView, SpectacularRedocView
from config.schema_views import PublicSchemaView, TenantSchemaView
from apps.core.views import swagger_landing
from apps.facilities import views as facilities_views

urlpatterns = [
    # API Documentation Landing Page
    path('', swagger_landing, name='api_root'),
    path('api/docs/', swagger_landing, name='swagger-landing'),
    
    # Admin panel
    path('admin/', admin.site.urls),
    
    # API Documentation - PUBLIC SCHEMA (Account Management)
    path('api/schema/public/', PublicSchemaView.as_view(), name='schema-public'),
    path('api/docs/public/', SpectacularSwaggerView.as_view(url_name='schema-public'), name='swagger-ui-public'),
    path('api/redoc/public/', SpectacularRedocView.as_view(url_name='schema-public'), name='redoc-public'),
    
    # API Documentation - TENANT SCHEMA (Company Operations)
    path('api/schema/tenant/', TenantSchemaView.as_view(), name='schema-tenant'),
    path('api/docs/tenant/', SpectacularSwaggerView.as_view(url_name='schema-tenant'), name='swagger-ui-tenant'),
    path('api/redoc/tenant/', SpectacularRedocView.as_view(url_name='schema-tenant'), name='redoc-tenant'),
    
    # API Endpoints (v1)
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/onboarding/', include('apps.tenants.urls')),
    path('api/v1/billing/', include('apps.billing.urls')),
    
    # Customer invitation endpoints (public - no tenant required)
    path('api/v1/customers/invitations/verify/', facilities_views.verify_customer_invitation, name='verify-customer-invitation-public'),
    path('api/v1/customers/invitations/accept/', facilities_views.accept_customer_invitation, name='accept-customer-invitation-public'),
    
    # Tenant-specific endpoints
    path('api/v1/', include('apps.facilities.urls')),
    path('api/v1/', include('apps.equipment.urls')),
    path('api/v1/tasks/', include('apps.tasks.urls')),
    path('api/v1/service-requests/', include('apps.service_requests.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/files/', include('apps.files.urls')),
    
    # Organization Dashboard (tenant-specific)
    path('api/v1/dashboard/', include('apps.tenants.urls_dashboard')),
    
    # Health check
    path('health/', include('apps.core.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)