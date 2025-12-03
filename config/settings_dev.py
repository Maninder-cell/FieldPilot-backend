"""
FieldRino Development Settings (SQLite)

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
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

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
    'apps.tenants.middleware.TenantMembershipMiddleware',  # Add tenant membership to request
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls_dev'

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
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # For browsable API
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        # Browsable API disabled - use Swagger UI instead
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.core.pagination.CustomPageNumberPagination',
    'PAGE_SIZE': 10,
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',  # OpenAPI schema
}

# drf-spectacular settings for Swagger/OpenAPI
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

## API Endpoints

- **Authentication**: User registration, login, profile management
- **Onboarding**: Company creation, team management
- **Billing**: Subscription plans, payments, invoices
- **Health**: System health monitoring

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
        }
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

# CORS Configuration - Allow all origins in development for multi-tenant subdomains
CORS_ALLOW_ALL_ORIGINS = True  # For development only
CORS_ALLOW_CREDENTIALS = True

# Alternative: Specific origins (uncomment if you want to restrict)
# CORS_ALLOWED_ORIGINS = [
#     'http://localhost:3000',
#     'http://127.0.0.1:3000',
#     'http://localhost:8000',
#     'http://127.0.0.1:8000',
#     'http://jumba.localhost:8000',
#     'http://amazon.localhost:8000',
#     'http://acme.localhost:8000',
# ]

# Allow all localhost subdomains using regex (more secure than ALLOW_ALL)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://.*\.localhost:\d+$",  # Allow any subdomain of localhost
]

# Email Configuration (MailHog for development)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='mailhog')  # Use 'mailhog' for Docker, 'localhost' for local
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'noreply@fieldrino.com'

# Celery Configuration
# Use 'redis' for Docker, 'localhost' for local development
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Cache Configuration (Local memory cache for development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 3600,  # 1 hour default
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
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
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Security Settings (relaxed for development)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Stripe Settings
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='whsec_dummy_secret')
