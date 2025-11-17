# Django-Tenants Schema-Per-Tenant Setup

## Overview

FieldRino now uses **django-tenants** for true schema-per-tenant multi-tenancy with PostgreSQL. Each tenant gets its own isolated PostgreSQL schema, ensuring complete data separation.

## What Changed

### 1. Models (`apps/tenants/models.py`)
- `Tenant` model now inherits from `TenantMixin`
- Added `schema_name` field for PostgreSQL schema identification
- Created `Domain` model (inherits from `DomainMixin`) for tenant routing
- Kept UUID as primary key for backward compatibility

### 2. Settings (`config/settings.py` and `config/settings_dev.py`)
- Database engine: `django_tenants.postgresql_backend`
- Configured `TENANT_MODEL` and `TENANT_DOMAIN_MODEL`
- Split apps into `SHARED_APPS` (public schema) and `TENANT_APPS` (tenant schemas)
- Added `TenantMainMiddleware` as first middleware
- Added `TenantSyncRouter` for database routing
- **Removed all SQLite support** - PostgreSQL is required

### 3. Database Structure
```
PostgreSQL Database
├── public schema (shared)
│   ├── tenants
│   ├── tenants_domains
│   ├── billing_*
│   └── auth_* (if shared)
├── tenant_acme schema
│   ├── authentication_user
│   ├── facilities_*
│   ├── equipment_*
│   └── tasks_*
└── tenant_xyz schema
    ├── authentication_user
    ├── facilities_*
    └── ...
```

## How It Works

1. **Request comes in** with a domain (e.g., `acme.fieldrino.com`)
2. **TenantMainMiddleware** looks up the tenant by domain
3. **PostgreSQL search_path** is set to the tenant's schema
4. **All queries** execute in that tenant's isolated schema
5. **Data is completely isolated** between tenants

## Usage

### Creating a New Tenant

```python
from apps.tenants.models import Tenant, Domain

# Create tenant (schema is auto-created)
tenant = Tenant.objects.create(
    schema_name='acme',  # Will be used as PostgreSQL schema name
    name='Acme Corporation',
    slug='acme'
)

# Create domain for routing
domain = Domain.objects.create(
    domain='acme.fieldrino.com',
    tenant=tenant,
    is_primary=True
)
```

### Running Migrations

```bash
# Migrate shared apps (public schema)
python manage.py migrate_schemas --shared

# Migrate all tenant schemas
python manage.py migrate_schemas

# Migrate specific tenant
python manage.py migrate_schemas --tenant=acme
```

### Switching Tenants in Code

```python
from django.db import connection
from apps.tenants.models import Tenant

# Get tenant
tenant = Tenant.objects.get(schema_name='acme')

# Switch to tenant's schema
connection.set_tenant(tenant)

# Now all queries use acme's schema
users = User.objects.all()  # Only acme's users
```

## Testing

Run the verification test:

```bash
python manage.py shell < test_tenants.py
```

Or manually:

```python
from apps.tenants.models import Tenant, Domain
from django.db import connection

# List all schemas
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT schema_name FROM information_schema.schemata 
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    """)
    print(cursor.fetchall())

# Test isolation
tenant1 = Tenant.objects.get(schema_name='tenant1')
tenant2 = Tenant.objects.get(schema_name='tenant2')

connection.set_tenant(tenant1)
print(f"Tenant1 users: {User.objects.count()}")

connection.set_tenant(tenant2)
print(f"Tenant2 users: {User.objects.count()}")
```

## Requirements

- **PostgreSQL 9.6+** (required)
- **django-tenants 3.6.1+**
- **psycopg2-binary 2.9+**

## Important Notes

1. **PostgreSQL Only**: SQLite is not supported for multi-tenancy
2. **Schema Names**: Must be valid PostgreSQL identifiers (lowercase, underscores)
3. **Public Tenant**: Always required with `schema_name='public'`
4. **Migrations**: Always run `migrate_schemas --shared` before `migrate_schemas`
5. **Domain Required**: Each tenant needs at least one domain for routing

## Verified Working

✓ Schema-per-tenant isolation  
✓ Automatic schema creation  
✓ Domain-based routing  
✓ Data isolation between tenants  
✓ Middleware switching  
✓ Both dev and production configs  

## Current Tenants

- **public** (localhost) - Required system tenant
- **jumba** - Existing tenant
- **amazon** - Existing tenant  
- **test_acme** (acme.localhost) - Test tenant

All tenants have isolated schemas with complete data separation.
