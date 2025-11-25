"""
FieldRino Django Settings

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""

import os
from pathlib import Path
from decouple import config
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Multi-tenancy configuration
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"

# Shared apps (available to all tenants)
SHARED_APPS = [
    'django_tenants',  # Must be first
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party shared
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    'django_celery_beat',  # Celery beat scheduler
    
    # Local shared apps
    'apps.core',
    'apps.tenants',
    'apps.billing',
    'apps.authentication',  # Shared - users can belong to multiple tenants
]

# Tenant-specific apps (isolated per tenant)
TENANT_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    
    # Local tenant apps
    'apps.facilities',
    'apps.equipment',
    'apps.tasks',
    'apps.maintenance',
    'apps.technicians',
    'apps.service_requests',
    'apps.inventory',
    'apps.notifications',
    'apps.analytics',
    'apps.reports',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',  # Must be first
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - PostgreSQL with django-tenants backend
import dj_database_url

DATABASE_URL = config('DATABASE_URL', default='postgresql://fieldrino_user:fieldrino_password@localhost:5432/fieldrino_db')

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Override engine to use django-tenants PostgreSQL backend
DATABASES['default']['ENGINE'] = 'django_tenants.postgresql_backend'

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.authentication.authentication.TenantJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular (Swagger/OpenAPI) Configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'FieldRino API',
    'DESCRIPTION': '''
# FieldRino API Documentation

AI-Powered Multi-Tenant Facility & Equipment Management SaaS Platform

## Getting Started

1. **Register** a new user account
2. **Verify** your email with OTP
3. **Login** to get JWT access token
4. **Create** your company/tenant
5. **Subscribe** to a plan
6. **Invite** team members

## Authentication

All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

Get your token by calling the `/api/v1/auth/login/` endpoint.

## Multi-Tenancy

This API uses subdomain-based multi-tenancy. Each tenant has their own subdomain:
- Development: `http://{tenant}.localhost:8000`
- Production: `https://{tenant}.fieldrino.com`

## Support

For support, contact: support@fieldrino.com
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    
    # Swagger UI settings
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 1,
        'defaultModelRendering': 'model',
        'displayRequestDuration': True,
        'docExpansion': 'none',
        'filter': True,
        'showExtensions': True,
        'showCommonExtensions': True,
        'syntaxHighlight.theme': 'monokai',
    },
    
    # Servers - Use relative URL to support multi-tenant subdomains
    'SERVERS': [
        {'url': '/', 'description': 'Current tenant (auto-detected)'},
    ],
    
    # Tags (organized by feature)
    'TAGS': [
        {
            'name': 'Authentication',
            'description': 'User registration, login, profile management, and password operations'
        },
        {
            'name': 'Onboarding',
            'description': 'Company/tenant creation, team member management, and onboarding flow'
        },
        {
            'name': 'Billing',
            'description': 'Subscription plans, payment methods, invoices, and billing management'
        },
        {
            'name': 'Customers',
            'description': 'Customer management, invitations, and access control'
        },
        {
            'name': 'Facilities',
            'description': 'Facility management and operations'
        },
        {
            'name': 'Buildings',
            'description': 'Building management within facilities'
        },
        {
            'name': 'Equipment',
            'description': 'Equipment tracking and management'
        },
        {
            'name': 'Tasks',
            'description': 'Task management, assignment, and status tracking for equipment maintenance'
        },
        {
            'name': 'Teams',
            'description': 'Technician team management and member operations'
        },
        {
            'name': 'Time Tracking',
            'description': 'Time tracking for technicians including travel, arrival, departure, and lunch breaks'
        },
        {
            'name': 'Comments',
            'description': 'Task comments and communication'
        },
        {
            'name': 'Attachments',
            'description': 'File attachments for tasks (images, documents)'
        },
        {
            'name': 'Materials',
            'description': 'Material tracking for tasks (needed vs received)'
        },
        {
            'name': 'Reports',
            'description': 'Work hours reports and analytics'
        },
    ],
    
    # Contact and license
    'CONTACT': {
        'name': 'FieldRino Support',
        'email': 'support@fieldrino.com',
        'url': 'https://fieldrino.com/support',
    },
    'LICENSE': {
        'name': 'Proprietary',
        'url': 'https://fieldrino.com/license',
    },
    
    # Schema generation settings
    'ENUM_NAME_OVERRIDES': {},
    'POSTPROCESSING_HOOKS': ['config.spectacular_hooks.postprocessing_hook'],
    'PREPROCESSING_HOOKS': [],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVE_AUTHENTICATION': None,
    
    # Component settings
    'COMPONENT_NO_READ_ONLY_REQUIRED': False,
    'CAMELIZE_NAMES': False,
    'SCHEMA_COERCE_PATH_PK': True,
    'SCHEMA_COERCE_METHOD_NAMES': {},
    
    # Security
    'SECURITY': [
        {
            'Bearer': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    ],
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=15, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
# In production, use environment variable to set allowed origins
# Example: CORS_ALLOWED_ORIGINS=https://app.fieldrino.com,https://admin.fieldrino.com
if DEBUG:
    # Development: Allow all localhost subdomains
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    # Production: Use specific origins from environment variable
    cors_origins = config('CORS_ALLOWED_ORIGINS', default='')
    if cors_origins:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
    else:
        CORS_ALLOWED_ORIGINS = []
    
    # Allow credentials for authenticated requests
    CORS_ALLOW_CREDENTIALS = True
    
    # Allow tenant subdomains using regex pattern
    # Example: *.fieldrino.com
    cors_domain = config('CORS_ALLOWED_DOMAIN', default='fieldrino.com')
    CORS_ALLOWED_ORIGIN_REGEXES = [
        rf"^https://.*\.{cors_domain}$",  # Allow any subdomain
        rf"^https://{cors_domain}$",       # Allow main domain
    ]

# Email Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@fieldrino.com')

# Celery Configuration
# Use 'redis' for Docker, 'localhost' for local development
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Stripe Configuration
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
    }
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Create logs directory
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
