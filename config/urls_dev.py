"""
FieldPilot Development URL Configuration

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # Redirect root to Swagger documentation
    path('', RedirectView.as_view(url='/api/docs/', permanent=False), name='api_root'),
    
    # Admin panel
    path('admin/', admin.site.urls),
    
    # API Documentation (Clean URLs)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Endpoints (v1)
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/onboarding/', include('apps.tenants.urls')),
    path('api/v1/billing/', include('apps.billing.urls')),
    path('api/v1/', include('apps.facilities.urls')),
    path('api/v1/', include('apps.equipment.urls')),
    
    # Health check
    path('health/', include('apps.core.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)