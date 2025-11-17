# FieldRino - Technical Architecture

## System Architecture Overview

FieldRino follows a modern microservices-inspired architecture with a clear separation between frontend, backend, and infrastructure layers. The system is designed for horizontal scalability, multi-tenancy, and high availability.

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web App    │  │  Mobile PWA  │  │  Admin Panel │      │
│  │  (Next.js)   │  │  (Next.js)   │  │  (Next.js)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway / Load Balancer              │
│                     (Nginx / AWS ALB)                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend Services                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Django REST Framework API                     │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │   Auth     │  │  Tenants   │  │  Equipment │     │  │
│  │  │  Service   │  │  Service   │  │  Service   │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │   Tasks    │  │  Billing   │  │  Reports   │     │  │
│  │  │  Service   │  │  Service   │  │  Service   │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │    Redis     │  │   AWS S3     │      │
│  │ (Multi-tenant│  │   (Cache &   │  │  (File       │      │
│  │   Schemas)   │  │    Queue)    │  │   Storage)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     Background Workers                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Celery    │  │  Celery Beat │  │   ML Models  │      │
│  │   Workers    │  │  (Scheduler) │  │  (Predictive)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Multi-Tenancy Architecture

### Strategy: Schema-Based Isolation

We use **django-tenants** for schema-based multi-tenancy, providing complete data isolation per tenant.

#### Database Structure

```
PostgreSQL Database: fieldrino_db
│
├── public schema (shared)
│   ├── tenants_tenant (tenant registry)
│   ├── tenants_domain (domain mapping)
│   └── subscriptions_plan (subscription plans)
│
├── tenant_acme_corp (Tenant 1)
│   ├── users
│   ├── equipment
│   ├── tasks
│   ├── facilities
│   └── ... (all tenant-specific tables)
│
├── tenant_xyz_services (Tenant 2)
│   ├── users
│   ├── equipment
│   └── ...
│
└── tenant_abc_facilities (Tenant 3)
    └── ...
```

#### Tenant Resolution Flow

```python
# 1. Request arrives with domain: acme.fieldrino.com
# 2. Middleware extracts subdomain: "acme"
# 3. Query public.tenants_domain to find tenant
# 4. Set PostgreSQL search_path to tenant schema
# 5. All queries now isolated to tenant schema
```

### Tenant Onboarding Flow

```
1. User signs up → POST /api/v1/auth/register
2. Create tenant record in public schema
3. Create dedicated schema for tenant
4. Run migrations on new schema
5. Create admin user in tenant schema
6. Initialize default data (roles, permissions)
7. Send verification email
8. Redirect to onboarding wizard
```

## Backend Architecture (Django)

### Project Structure

```
backend/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── tenants/
│   │   ├── models.py (Tenant, Domain)
│   │   ├── middleware.py
│   │   └── utils.py
│   ├── authentication/
│   │   ├── models.py (User, Role, Permission)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── jwt_auth.py
│   ├── facilities/
│   │   ├── models.py (Location, Facility, Building)
│   │   ├── serializers.py
│   │   └── views.py
│   ├── equipment/
│   │   ├── models.py (Equipment, EquipmentType)
│   │   ├── serializers.py
│   │   └── views.py
│   ├── tasks/
│   │   ├── models.py (Task, TaskComment, TaskAttachment)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── signals.py
│   ├── maintenance/
│   │   ├── models.py (MaintenanceSchedule)
│   │   ├── tasks.py (Celery tasks)
│   │   └── views.py
│   ├── technicians/
│   │   ├── models.py (TechnicianProfile, WorkLog)
│   │   ├── serializers.py
│   │   └── views.py
│   ├── inventory/
│   │   ├── models.py (Part, Stock, PurchaseOrder)
│   │   └── views.py
│   ├── billing/
│   │   ├── models.py (Subscription, Invoice, Payment)
│   │   ├── stripe_webhooks.py
│   │   └── views.py
│   ├── notifications/
│   │   ├── models.py (Notification, PushSubscription)
│   │   ├── tasks.py
│   │   └── push_notifications.py
│   ├── analytics/
│   │   ├── models.py (Report, Dashboard)
│   │   ├── views.py
│   │   └── ml_models.py
│   └── integrations/
│       ├── calendar_sync.py
│       ├── slack_integration.py
│       └── webhooks.py
├── core/
│   ├── permissions.py
│   ├── pagination.py
│   ├── exceptions.py
│   └── utils.py
├── tests/
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── Dockerfile
├── docker-compose.yml
└── manage.py
```

### Key Django Packages

```txt
# Core
Django==4.2.x
djangorestframework==3.14.x
django-tenants==3.5.x
psycopg2-binary==2.9.x

# Authentication & Security
djangorestframework-simplejwt==5.3.x
django-cors-headers==4.3.x
django-oauth-toolkit==2.3.x

# Async & Background Tasks
celery==5.3.x
django-celery-beat==2.5.x
redis==5.0.x

# File Storage
django-storages==1.14.x
boto3==1.28.x

# API Documentation
drf-spectacular==0.26.x

# Payments
stripe==7.0.x

# Monitoring & Logging
sentry-sdk==1.38.x
django-debug-toolbar==4.2.x

# Testing
pytest-django==4.7.x
factory-boy==3.3.x
```

### API Design Principles

#### RESTful Endpoints

```
# Authentication
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/password-reset

# Tenants (Public Schema)
POST   /api/v1/tenants/
GET    /api/v1/tenants/{id}/

# Equipment
GET    /api/v1/equipment/
POST   /api/v1/equipment/
GET    /api/v1/equipment/{id}/
PUT    /api/v1/equipment/{id}/
PATCH  /api/v1/equipment/{id}/
DELETE /api/v1/equipment/{id}/
GET    /api/v1/equipment/{id}/maintenance-history/
POST   /api/v1/equipment/{id}/shutdown/

# Tasks
GET    /api/v1/tasks/
POST   /api/v1/tasks/
GET    /api/v1/tasks/{id}/
PUT    /api/v1/tasks/{id}/
PATCH  /api/v1/tasks/{id}/status/
POST   /api/v1/tasks/{id}/comments/
POST   /api/v1/tasks/{id}/attachments/
GET    /api/v1/tasks/overdue/
GET    /api/v1/tasks/my-tasks/

# Maintenance Schedules
GET    /api/v1/maintenance-schedules/
POST   /api/v1/maintenance-schedules/
GET    /api/v1/maintenance-schedules/{id}/
PUT    /api/v1/maintenance-schedules/{id}/
DELETE /api/v1/maintenance-schedules/{id}/

# Billing
GET    /api/v1/billing/subscription/
POST   /api/v1/billing/subscription/upgrade/
POST   /api/v1/billing/subscription/cancel/
GET    /api/v1/billing/invoices/
POST   /api/v1/billing/payment-method/
POST   /api/v1/billing/webhooks/stripe/

# Analytics
GET    /api/v1/analytics/dashboard/
GET    /api/v1/analytics/reports/
POST   /api/v1/analytics/reports/generate/
GET    /api/v1/analytics/equipment-health/
GET    /api/v1/analytics/predictions/

# Webhooks (Outgoing)
GET    /api/v1/webhooks/
POST   /api/v1/webhooks/
DELETE /api/v1/webhooks/{id}/
```

#### Response Format

```json
{
  "success": true,
  "data": {
    "id": 123,
    "name": "Equipment Name"
  },
  "meta": {
    "timestamp": "2025-10-29T10:30:00Z",
    "version": "1.0"
  }
}
```

#### Error Format

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field_name": ["This field is required"]
    }
  },
  "meta": {
    "timestamp": "2025-10-29T10:30:00Z"
  }
}
```

## Frontend Architecture (Next.js)

### Project Structure

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   ├── register/
│   │   └── forgot-password/
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── equipment/
│   │   ├── tasks/
│   │   ├── maintenance/
│   │   ├── technicians/
│   │   ├── inventory/
│   │   ├── reports/
│   │   └── settings/
│   ├── (mobile)/
│   │   ├── technician/
│   │   └── customer/
│   ├── api/
│   │   └── [...proxy]/route.ts
│   └── layout.tsx
├── components/
│   ├── ui/
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   └── Footer.tsx
│   ├── equipment/
│   │   ├── EquipmentList.tsx
│   │   ├── EquipmentCard.tsx
│   │   └── EquipmentForm.tsx
│   ├── tasks/
│   │   ├── TaskList.tsx
│   │   ├── TaskCard.tsx
│   │   └── TaskForm.tsx
│   └── charts/
│       ├── LineChart.tsx
│       └── BarChart.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── equipment.ts
│   │   ├── tasks.ts
│   │   └── auth.ts
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useEquipment.ts
│   │   └── useTasks.ts
│   ├── store/
│   │   ├── authStore.ts
│   │   └── uiStore.ts
│   └── utils/
│       ├── formatters.ts
│       └── validators.ts
├── types/
│   ├── equipment.ts
│   ├── task.ts
│   └── user.ts
├── public/
│   ├── manifest.json
│   ├── sw.js
│   └── icons/
├── styles/
│   └── globals.css
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

### Key Frontend Packages

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "tailwindcss": "^3.3.0",
    "framer-motion": "^10.16.0",
    "react-hook-form": "^7.48.0",
    "zod": "^3.22.0",
    "date-fns": "^2.30.0",
    "recharts": "^2.10.0",
    "react-hot-toast": "^2.4.0",
    "next-pwa": "^5.6.0"
  }
}
```

## Database Schema Design

### Core Tables (Tenant Schema)

```sql
-- Users & Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) NOT NULL,
    employee_id VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Facilities
CREATE TABLE facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(100),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Equipment
CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID REFERENCES facilities(id) ON DELETE CASCADE,
    equipment_number VARCHAR(100) UNIQUE NOT NULL,
    serial_number VARCHAR(255),
    registration_number VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    equipment_type VARCHAR(100),
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    capacity VARCHAR(100),
    speed VARCHAR(100),
    controller VARCHAR(255),
    installation_date DATE,
    status VARCHAR(50) DEFAULT 'operational',
    health_score INTEGER DEFAULT 100,
    last_maintenance_date TIMESTAMP,
    next_maintenance_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'new',
    due_date TIMESTAMP,
    assigned_to UUID REFERENCES users(id),
    assigned_team UUID REFERENCES teams(id),
    created_by UUID REFERENCES users(id),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Maintenance Schedules
CREATE TABLE maintenance_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    schedule_name VARCHAR(255) NOT NULL,
    frequency_days INTEGER NOT NULL,
    last_run_date TIMESTAMP,
    next_run_date TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    task_template JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Inventory
CREATE TABLE inventory_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    unit_price DECIMAL(10, 2),
    quantity_in_stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 10,
    supplier VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Public Schema Tables

```sql
-- Tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_name VARCHAR(63) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Domains
CREATE TABLE domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    domain VARCHAR(255) UNIQUE NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Subscription Plans
CREATE TABLE subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    price_monthly DECIMAL(10, 2),
    price_yearly DECIMAL(10, 2),
    max_users INTEGER,
    max_equipment INTEGER,
    features JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES subscription_plans(id),
    stripe_subscription_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Caching Strategy

### Redis Cache Layers

```python
# Layer 1: API Response Cache (5 minutes)
cache.set(f"equipment:list:{tenant_id}", equipment_data, 300)

# Layer 2: Database Query Cache (15 minutes)
cache.set(f"equipment:{equipment_id}", equipment_obj, 900)

# Layer 3: Computed Data Cache (1 hour)
cache.set(f"analytics:dashboard:{tenant_id}", dashboard_data, 3600)

# Layer 4: Session Cache (24 hours)
cache.set(f"session:{user_id}", session_data, 86400)
```

### Cache Invalidation

```python
# Invalidate on write operations
@receiver(post_save, sender=Equipment)
def invalidate_equipment_cache(sender, instance, **kwargs):
    cache.delete(f"equipment:{instance.id}")
    cache.delete(f"equipment:list:{instance.tenant_id}")
```

## Security Architecture

### Authentication Flow

```
1. User submits credentials → POST /api/v1/auth/login
2. Backend validates credentials
3. Generate JWT access token (15 min expiry)
4. Generate JWT refresh token (7 days expiry)
5. Return both tokens to client
6. Client stores tokens (httpOnly cookies or localStorage)
7. Client includes access token in Authorization header
8. Backend validates token on each request
9. When access token expires, use refresh token
10. Refresh endpoint returns new access token
```

### Permission System

```python
# Role-based permissions
ROLES = {
    'admin': ['*'],  # All permissions
    'manager': ['view_*', 'create_*', 'update_*'],
    'technician': ['view_tasks', 'update_tasks', 'view_equipment'],
    'customer': ['view_own_requests', 'create_service_request']
}

# Permission decorator
@permission_required('update_equipment')
def update_equipment(request, equipment_id):
    # Only users with 'update_equipment' permission can access
    pass
```

### Data Encryption

- **At Rest**: PostgreSQL with AES-256 encryption
- **In Transit**: TLS 1.3 for all API communications
- **Sensitive Fields**: Additional field-level encryption for PII
- **File Storage**: S3 server-side encryption (SSE-S3)

## Deployment Architecture

### Production Infrastructure (AWS)

```
┌─────────────────────────────────────────────────────────┐
│                    Route 53 (DNS)                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              CloudFront (CDN) + WAF                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│         Application Load Balancer (ALB)                  │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│   ECS Fargate    │           │   ECS Fargate    │
│  (Next.js App)   │           │  (Django API)    │
│  Auto-scaling    │           │  Auto-scaling    │
└──────────────────┘           └──────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
          ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
          │  RDS Postgres│    │ ElastiCache  │   │   S3 Bucket  │
          │ Multi-AZ     │    │   (Redis)    │   │ (File Store) │
          └──────────────┘    └──────────────┘   └──────────────┘
```

### Container Configuration

```dockerfile
# Django Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

```dockerfile
# Next.js Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

## Monitoring & Observability

### Metrics to Track

```python
# Application Metrics
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Database query time
- Cache hit rate
- Celery task queue length
- Active WebSocket connections

# Business Metrics
- Active tenants
- Daily/Monthly active users
- Task completion rate
- Equipment uptime
- API usage per tenant
- Subscription churn rate
```

### Logging Strategy

```python
# Structured logging with context
logger.info(
    "Task created",
    extra={
        "tenant_id": tenant.id,
        "user_id": user.id,
        "task_id": task.id,
        "equipment_id": equipment.id,
        "priority": task.priority
    }
)
```

## Performance Optimization

### Database Optimization

```python
# Use select_related for foreign keys
Equipment.objects.select_related('facility', 'created_by')

# Use prefetch_related for reverse foreign keys
Facility.objects.prefetch_related('equipment_set')

# Database indexes
class Equipment(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['facility_id', 'status']),
            models.Index(fields=['next_maintenance_date']),
        ]
```

### API Optimization

```python
# Pagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

# Field filtering
GET /api/v1/equipment/?fields=id,name,status

# Response compression
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',
]
```

## Scalability Considerations

### Horizontal Scaling

- **Stateless API servers**: Can add/remove instances dynamically
- **Database read replicas**: Distribute read load across replicas
- **Redis cluster**: Shard cache across multiple nodes
- **Celery workers**: Scale workers based on queue length

### Vertical Scaling

- **Database**: Upgrade RDS instance type as needed
- **Cache**: Increase ElastiCache node size
- **Compute**: Increase ECS task CPU/memory

### Cost Optimization

- **Auto-scaling**: Scale down during off-peak hours
- **Reserved instances**: 1-year commitment for 40% savings
- **S3 lifecycle policies**: Move old files to Glacier
- **CloudFront**: Reduce origin requests with aggressive caching

## Disaster Recovery

### Backup Strategy

```
- Database: Automated daily backups, 30-day retention
- Files: S3 versioning enabled, cross-region replication
- Configuration: Infrastructure as Code (Terraform)
- Recovery Time Objective (RTO): 4 hours
- Recovery Point Objective (RPO): 1 hour
```

### High Availability

```
- Multi-AZ deployment for database
- Auto-scaling groups with min 2 instances
- Health checks and automatic failover
- 99.9% uptime SLA
```
