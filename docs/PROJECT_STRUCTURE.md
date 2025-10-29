# FieldPilot - Project Structure

## Overview

This document provides a comprehensive overview of the FieldPilot project structure, explaining the purpose of each directory and file.

## Root Directory Structure

```
fieldpilot/
├── backend/                 # Django backend application
├── frontend/                # Next.js frontend application
├── docs/                    # Project documentation
├── .github/                 # GitHub workflows and templates
├── docker-compose.yml       # Docker Compose configuration
├── .gitignore              # Git ignore rules
├── README.md               # Project overview
└── LICENSE                 # License file
```

## Backend Structure

```
backend/
├── config/                          # Django project configuration
│   ├── settings/
│   │   ├── base.py                 # Base settings
│   │   ├── development.py          # Development settings
│   │   ├── production.py           # Production settings
│   │   └── test.py                 # Test settings
│   ├── urls.py                     # Root URL configuration
│   ├── wsgi.py                     # WSGI configuration
│   └── asgi.py                     # ASGI configuration (WebSocket)
│
├── apps/                            # Django applications
│   ├── tenants/                    # Multi-tenancy management
│   │   ├── models.py               # Tenant, Domain models
│   │   ├── middleware.py           # Tenant resolution middleware
│   │   ├── management/             # Management commands
│   │   │   └── commands/
│   │   │       └── create_tenant.py
│   │   └── tests/
│   │
│   ├── authentication/             # User authentication
│   │   ├── models.py               # User, Role, Permission models
│   │   ├── serializers.py          # User serializers
│   │   ├── views.py                # Auth endpoints
│   │   ├── jwt_auth.py             # JWT authentication
│   │   └── tests/
│   │
│   ├── facilities/                 # Facility management
│   │   ├── models.py               # Facility, Building models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests/
│   │
│   ├── equipment/                  # Equipment management
│   │   ├── models.py               # Equipment, EquipmentImage models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── filters.py              # Equipment filters
│   │   ├── utils.py                # Helper functions
│   │   └── tests/
│   │
│   ├── tasks/                      # Task management
│   │   ├── models.py               # Task, TaskComment models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── signals.py              # Task signals
│   │   └── tests/
│   │
│   ├── maintenance/                # Scheduled maintenance
│   │   ├── models.py               # MaintenanceSchedule model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py                # Celery tasks
│   │   └── tests/
│   │
│   ├── technicians/                # Technician operations
│   │   ├── models.py               # TechnicianProfile, WorkLog
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests/
│   │
│   ├── service_requests/           # Service request management
│   │   ├── models.py               # ServiceRequest model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests/
│   │
│   ├── inventory/                  # Inventory management
│   │   ├── models.py               # Part, Stock, Transaction models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── tests/
│   │
│   ├── billing/                    # Subscription & billing
│   │   ├── models.py               # Subscription, Invoice models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── stripe_webhooks.py      # Stripe webhook handlers
│   │   └── tests/
│   │
│   ├── notifications/              # Notification system
│   │   ├── models.py               # Notification, PushSubscription
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py                # Notification tasks
│   │   ├── push_notifications.py   # Push notification logic
│   │   └── tests/
│   │
│   ├── analytics/                  # Analytics & reporting
│   │   ├── models.py               # Report, Dashboard models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── ml_models.py            # ML prediction models
│   │   └── tests/
│   │
│   └── integrations/               # Third-party integrations
│       ├── calendar_sync.py        # Calendar integration
│       ├── slack_integration.py    # Slack integration
│       ├── webhooks.py             # Outgoing webhooks
│       └── tests/
│
├── core/                            # Core utilities
│   ├── permissions.py              # Custom permissions
│   ├── pagination.py               # Pagination classes
│   ├── exceptions.py               # Custom exceptions
│   ├── throttling.py               # Rate limiting
│   └── utils.py                    # Helper functions
│
├── tests/                           # Integration tests
│   ├── test_multi_tenancy.py
│   ├── test_api_endpoints.py
│   └── test_workflows.py
│
├── requirements/                    # Python dependencies
│   ├── base.txt                    # Base requirements
│   ├── development.txt             # Dev requirements
│   ├── production.txt              # Production requirements
│   └── test.txt                    # Test requirements
│
├── static/                          # Static files
├── media/                           # User-uploaded files (dev only)
├── templates/                       # Email templates
│   ├── emails/
│   │   ├── welcome.html
│   │   ├── task_assigned.html
│   │   └── password_reset.html
│   └── admin/                      # Admin customization
│
├── scripts/                         # Utility scripts
│   ├── lint.sh                     # Linting script
│   ├── test.sh                     # Testing script
│   └── deploy.sh                   # Deployment script
│
├── Dockerfile                       # Docker configuration
├── Dockerfile.prod                  # Production Docker config
├── .env.example                     # Environment variables template
├── manage.py                        # Django management script
├── pytest.ini                       # Pytest configuration
└── .coveragerc                      # Coverage configuration
```

## Frontend Structure

```
frontend/
├── app/                             # Next.js App Router
│   ├── (auth)/                     # Auth route group
│   │   ├── login/
│   │   │   └── page.tsx            # Login page
│   │   ├── register/
│   │   │   └── page.tsx            # Registration page
│   │   ├── forgot-password/
│   │   │   └── page.tsx            # Password reset page
│   │   └── layout.tsx              # Auth layout
│   │
│   ├── (dashboard)/                # Dashboard route group
│   │   ├── layout.tsx              # Dashboard layout
│   │   ├── page.tsx                # Dashboard home
│   │   │
│   │   ├── equipment/              # Equipment pages
│   │   │   ├── page.tsx            # Equipment list
│   │   │   ├── [id]/
│   │   │   │   └── page.tsx        # Equipment detail
│   │   │   └── new/
│   │   │       └── page.tsx        # Create equipment
│   │   │
│   │   ├── tasks/                  # Task pages
│   │   │   ├── page.tsx            # Task list
│   │   │   ├── [id]/
│   │   │   │   └── page.tsx        # Task detail
│   │   │   └── new/
│   │   │       └── page.tsx        # Create task
│   │   │
│   │   ├── maintenance/            # Maintenance pages
│   │   │   ├── page.tsx            # Schedule list
│   │   │   └── new/
│   │   │       └── page.tsx        # Create schedule
│   │   │
│   │   ├── inventory/              # Inventory pages
│   │   │   ├── page.tsx            # Parts list
│   │   │   └── transactions/
│   │   │       └── page.tsx        # Transaction history
│   │   │
│   │   ├── reports/                # Reports pages
│   │   │   ├── page.tsx            # Reports dashboard
│   │   │   └── [type]/
│   │   │       └── page.tsx        # Specific report
│   │   │
│   │   ├── settings/               # Settings pages
│   │   │   ├── page.tsx            # General settings
│   │   │   ├── profile/
│   │   │   │   └── page.tsx        # User profile
│   │   │   ├── team/
│   │   │   │   └── page.tsx        # Team management
│   │   │   ├── billing/
│   │   │   │   └── page.tsx        # Billing settings
│   │   │   └── notifications/
│   │   │       └── page.tsx        # Notification settings
│   │   │
│   │   └── admin/                  # Admin pages
│   │       ├── page.tsx            # Admin dashboard
│   │       └── tenants/
│   │           └── page.tsx        # Tenant management
│   │
│   ├── (mobile)/                   # Mobile route group
│   │   ├── technician/             # Technician mobile app
│   │   │   ├── page.tsx            # Task list (mobile)
│   │   │   └── tasks/
│   │   │       └── [id]/
│   │   │           └── page.tsx    # Task detail (mobile)
│   │   └── customer/               # Customer mobile app
│   │       └── page.tsx            # Service requests
│   │
│   ├── api/                        # API routes (if needed)
│   │   └── [...proxy]/
│   │       └── route.ts            # API proxy
│   │
│   ├── layout.tsx                  # Root layout
│   ├── page.tsx                    # Home page
│   ├── loading.tsx                 # Loading state
│   ├── error.tsx                   # Error boundary
│   └── not-found.tsx               # 404 page
│
├── components/                      # React components
│   ├── ui/                         # Base UI components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   ├── Card.tsx
│   │   ├── Table.tsx
│   │   ├── Dropdown.tsx
│   │   ├── Tabs.tsx
│   │   └── ...
│   │
│   ├── layout/                     # Layout components
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── Footer.tsx
│   │   └── MobileNav.tsx
│   │
│   ├── equipment/                  # Equipment components
│   │   ├── EquipmentList.tsx
│   │   ├── EquipmentCard.tsx
│   │   ├── EquipmentForm.tsx
│   │   ├── EquipmentDetails.tsx
│   │   └── EquipmentFilters.tsx
│   │
│   ├── tasks/                      # Task components
│   │   ├── TaskList.tsx
│   │   ├── TaskCard.tsx
│   │   ├── TaskForm.tsx
│   │   ├── TaskDetails.tsx
│   │   ├── TaskComments.tsx
│   │   └── TaskStatusBadge.tsx
│   │
│   ├── charts/                     # Chart components
│   │   ├── LineChart.tsx
│   │   ├── BarChart.tsx
│   │   ├── PieChart.tsx
│   │   └── HealthScoreGauge.tsx
│   │
│   └── forms/                      # Form components
│       ├── FormField.tsx
│       ├── FormSelect.tsx
│       ├── FormDatePicker.tsx
│       └── FormFileUpload.tsx
│
├── lib/                             # Utilities and helpers
│   ├── api/                        # API client
│   │   ├── client.ts               # Axios/fetch client
│   │   ├── equipment.ts            # Equipment API
│   │   ├── tasks.ts                # Tasks API
│   │   ├── auth.ts                 # Auth API
│   │   └── ...
│   │
│   ├── hooks/                      # Custom React hooks
│   │   ├── useAuth.ts              # Auth hook
│   │   ├── useEquipment.ts         # Equipment hook
│   │   ├── useTasks.ts             # Tasks hook
│   │   ├── useNotifications.ts     # Notifications hook
│   │   └── ...
│   │
│   ├── store/                      # State management
│   │   ├── authStore.ts            # Auth state (Zustand)
│   │   ├── uiStore.ts              # UI state
│   │   └── notificationStore.ts    # Notification state
│   │
│   └── utils/                      # Utility functions
│       ├── formatters.ts           # Date, number formatters
│       ├── validators.ts           # Form validators
│       ├── constants.ts            # Constants
│       └── helpers.ts              # Helper functions
│
├── types/                           # TypeScript types
│   ├── equipment.ts                # Equipment types
│   ├── task.ts                     # Task types
│   ├── user.ts                     # User types
│   ├── api.ts                      # API response types
│   └── index.ts                    # Type exports
│
├── public/                          # Static assets
│   ├── icons/                      # Icon files
│   ├── images/                     # Image files
│   ├── manifest.json               # PWA manifest
│   ├── sw.js                       # Service worker
│   └── robots.txt                  # Robots.txt
│
├── styles/                          # Global styles
│   └── globals.css                 # Global CSS
│
├── tests/                           # Tests
│   ├── components/                 # Component tests
│   ├── hooks/                      # Hook tests
│   ├── utils/                      # Utility tests
│   └── e2e/                        # E2E tests
│
├── .env.example                     # Environment variables template
├── .env.local                       # Local environment (gitignored)
├── next.config.js                   # Next.js configuration
├── tailwind.config.js               # Tailwind configuration
├── tsconfig.json                    # TypeScript configuration
├── package.json                     # NPM dependencies
├── jest.config.js                   # Jest configuration
├── .eslintrc.json                   # ESLint configuration
├── .prettierrc                      # Prettier configuration
├── Dockerfile                       # Docker configuration
└── Dockerfile.prod                  # Production Docker config
```

## Documentation Structure

```
docs/
├── README.md                        # Documentation index
├── PRODUCT_VISION.md                # Product vision and strategy
├── TECHNICAL_ARCHITECTURE.md        # System architecture
├── DATABASE_SCHEMA.md               # Database design
├── DEVELOPMENT_GUIDE.md             # Development setup
├── DEPLOYMENT.md                    # Deployment guide
├── SECURITY.md                      # Security documentation
├── MVP_SPRINT_PLAN.md               # Sprint planning
├── CONTRIBUTING.md                  # Contribution guidelines
└── PROJECT_STRUCTURE.md             # This file
```

## Configuration Files

### Root Level

- **docker-compose.yml**: Multi-container Docker setup for development
- **.gitignore**: Files and directories to ignore in Git
- **README.md**: Project overview and quick start guide
- **LICENSE**: Software license

### Backend

- **.env.example**: Template for environment variables
- **manage.py**: Django management command interface
- **pytest.ini**: Pytest configuration
- **.coveragerc**: Code coverage configuration
- **Dockerfile**: Development Docker image
- **Dockerfile.prod**: Production Docker image

### Frontend

- **next.config.js**: Next.js configuration
- **tailwind.config.js**: Tailwind CSS configuration
- **tsconfig.json**: TypeScript compiler options
- **package.json**: NPM dependencies and scripts
- **jest.config.js**: Jest testing configuration
- **.eslintrc.json**: ESLint linting rules
- **.prettierrc**: Prettier formatting rules

## Key Directories Explained

### Backend Apps

Each Django app follows a consistent structure:
- **models.py**: Database models
- **serializers.py**: DRF serializers for API
- **views.py**: API views/viewsets
- **urls.py**: URL routing (if needed)
- **tests/**: Unit and integration tests
- **admin.py**: Django admin customization
- **signals.py**: Django signals (if needed)
- **tasks.py**: Celery tasks (if needed)

### Frontend Components

Components are organized by feature:
- **ui/**: Reusable UI components (buttons, inputs, etc.)
- **layout/**: Layout components (header, sidebar, etc.)
- **feature/**: Feature-specific components (equipment, tasks, etc.)
- **forms/**: Form-related components
- **charts/**: Data visualization components

### API Client

The API client is organized by resource:
- Each file exports functions for CRUD operations
- Uses axios or fetch for HTTP requests
- Handles authentication tokens
- Provides TypeScript types for responses

## File Naming Conventions

### Backend (Python)

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case()`
- **Constants**: `UPPER_SNAKE_CASE`

### Frontend (TypeScript)

- **Components**: `PascalCase.tsx`
- **Utilities**: `camelCase.ts`
- **Types**: `PascalCase` interfaces
- **Constants**: `UPPER_SNAKE_CASE`

## Import Order

### Python

```python
# Standard library
import os
import sys

# Third-party
from django.db import models
from rest_framework import serializers

# Local
from apps.core.models import BaseModel
from apps.equipment.utils import generate_number
```

### TypeScript

```typescript
// React
import React from 'react';

// Third-party
import { useQuery } from '@tanstack/react-query';

// Components
import { Button } from '@/components/ui/Button';

// Utils
import { formatDate } from '@/lib/utils/formatters';

// Types
import type { Equipment } from '@/types/equipment';
```

## Environment Variables

### Backend (.env)

```bash
# Django
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/fieldpilot_db

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=fieldpilot-dev

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password
```

### Frontend (.env.local)

```bash
# API
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Google Maps
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your-api-key

# Environment
NEXT_PUBLIC_ENV=development
```

## Build Artifacts

### Backend

- **__pycache__/**: Python bytecode cache
- **.pytest_cache/**: Pytest cache
- **htmlcov/**: Coverage HTML reports
- **static/**: Collected static files
- **media/**: User uploads (dev only)

### Frontend

- **.next/**: Next.js build output
- **node_modules/**: NPM dependencies
- **out/**: Static export output
- **coverage/**: Test coverage reports

## Version Control

### Ignored Files

- Environment files (`.env`, `.env.local`)
- Build artifacts (`.next/`, `__pycache__/`)
- Dependencies (`node_modules/`, `venv/`)
- IDE files (`.vscode/`, `.idea/`)
- OS files (`.DS_Store`, `Thumbs.db`)
- Logs (`*.log`)
- Database files (`*.sqlite3`)

### Tracked Files

- Source code
- Configuration files
- Documentation
- Tests
- Docker files
- CI/CD workflows

## Deployment Structure

### Production

```
AWS Infrastructure
├── ECS Cluster
│   ├── Backend Service (Django)
│   ├── Frontend Service (Next.js)
│   ├── Celery Worker Service
│   └── Celery Beat Service
├── RDS PostgreSQL
├── ElastiCache Redis
├── S3 Buckets
│   ├── Static files
│   └── User uploads
├── CloudFront CDN
└── Application Load Balancer
```

## Additional Resources

- [Django Project Structure Best Practices](https://docs.djangoproject.com/en/4.2/intro/reusable-apps/)
- [Next.js Project Structure](https://nextjs.org/docs/getting-started/project-structure)
- [12-Factor App Methodology](https://12factor.net/)

---

**Last Updated**: October 29, 2025
