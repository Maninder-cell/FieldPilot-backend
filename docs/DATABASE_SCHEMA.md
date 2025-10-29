# FieldPilot - Database Schema Design

## Schema Overview

FieldPilot uses a **schema-based multi-tenancy** approach with PostgreSQL. Each tenant gets a dedicated schema for complete data isolation, while shared data (tenant registry, subscription plans) lives in the public schema.

## Multi-Tenancy Structure

```
fieldpilot_db (Database)
│
├── public (Shared Schema)
│   ├── tenants
│   ├── domains
│   ├── subscription_plans
│   ├── subscriptions
│   └── invoices
│
├── tenant_acme_corp (Tenant Schema 1)
│   ├── users
│   ├── facilities
│   ├── equipment
│   ├── tasks
│   └── ... (all tenant tables)
│
├── tenant_xyz_services (Tenant Schema 2)
│   └── ... (isolated data)
│
└── tenant_abc_facilities (Tenant Schema 3)
    └── ... (isolated data)
```

## Public Schema (Shared Tables)

### tenants

```sql
CREATE TABLE public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_name VARCHAR(63) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    company_size VARCHAR(50),
    industry VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    trial_ends_at TIMESTAMP,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON public.tenants(slug);
CREATE INDEX idx_tenants_active ON public.tenants(is_active);
```

### domains

```sql
CREATE TABLE public.domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    domain VARCHAR(255) UNIQUE NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_domains_tenant ON public.domains(tenant_id);
CREATE UNIQUE INDEX idx_domains_primary ON public.domains(tenant_id, is_primary) 
    WHERE is_primary = TRUE;
```

### subscription_plans

```sql
CREATE TABLE public.subscription_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    price_monthly DECIMAL(10, 2) NOT NULL,
    price_yearly DECIMAL(10, 2) NOT NULL,
    
    -- Limits
    max_users INTEGER,
    max_equipment INTEGER,
    max_storage_gb INTEGER,
    max_api_calls_per_month INTEGER,
    
    -- Features (JSONB for flexibility)
    features JSONB DEFAULT '{}',
    
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Example features JSON:
-- {
--   "ai_insights": true,
--   "predictive_maintenance": true,
--   "white_label": false,
--   "sso": false,
--   "api_access": true,
--   "priority_support": true,
--   "custom_workflows": false
-- }
```

### subscriptions

```sql
CREATE TABLE public.subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.subscription_plans(id),
    
    -- Stripe integration
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    
    status VARCHAR(50) DEFAULT 'active',
    -- Status: active, past_due, canceled, trialing, incomplete
    
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    -- Billing cycle: monthly, yearly
    
    current_period_start TIMESTAMP NOT NULL,
    current_period_end TIMESTAMP NOT NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    canceled_at TIMESTAMP,
    
    -- Usage tracking
    current_users_count INTEGER DEFAULT 0,
    current_equipment_count INTEGER DEFAULT 0,
    current_storage_gb DECIMAL(10, 2) DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_tenant ON public.subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_status ON public.subscriptions(status);
CREATE INDEX idx_subscriptions_stripe ON public.subscriptions(stripe_subscription_id);
```

### invoices

```sql
CREATE TABLE public.invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES public.subscriptions(id),
    
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    stripe_invoice_id VARCHAR(255),
    
    amount DECIMAL(10, 2) NOT NULL,
    tax DECIMAL(10, 2) DEFAULT 0,
    total DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    
    status VARCHAR(50) DEFAULT 'draft',
    -- Status: draft, open, paid, void, uncollectible
    
    due_date DATE,
    paid_at TIMESTAMP,
    
    invoice_pdf_url TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_invoices_tenant ON public.invoices(tenant_id);
CREATE INDEX idx_invoices_status ON public.invoices(status);
```

## Tenant Schema (Per-Tenant Tables)

### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    avatar_url TEXT,
    
    role VARCHAR(50) NOT NULL DEFAULT 'employee',
    -- Roles: admin, manager, employee, technician, customer
    
    employee_id VARCHAR(50) UNIQUE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    email_verified_at TIMESTAMP,
    
    -- 2FA
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_secret VARCHAR(255),
    
    -- Timestamps
    last_login_at TIMESTAMP,
    password_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_employee_id ON users(employee_id);
```

### user_permissions

```sql
CREATE TABLE user_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_permissions_user ON user_permissions(user_id);
CREATE UNIQUE INDEX idx_user_permissions_unique ON user_permissions(user_id, permission);
```

### teams

```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    team_lead_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_team_members_unique ON team_members(team_id, user_id);
```

### facilities

```sql
CREATE TABLE facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    facility_code VARCHAR(50) UNIQUE,
    facility_type VARCHAR(100),
    
    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    zip_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'USA',
    
    -- Geolocation
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Contact
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_facilities_type ON facilities(facility_type);
CREATE INDEX idx_facilities_active ON facilities(is_active);
```

### buildings

```sql
CREATE TABLE buildings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    building_code VARCHAR(50),
    floor_count INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_buildings_facility ON buildings(facility_id);
```

### equipment

```sql
CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    building_id UUID REFERENCES buildings(id) ON DELETE SET NULL,
    
    -- Identification
    equipment_number VARCHAR(100) UNIQUE NOT NULL,
    serial_number VARCHAR(255),
    registration_number VARCHAR(255),
    qr_code VARCHAR(255) UNIQUE,
    
    -- Basic Info
    name VARCHAR(255) NOT NULL,
    equipment_type VARCHAR(100),
    category VARCHAR(100),
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    
    -- Specifications
    capacity VARCHAR(100),
    speed VARCHAR(100),
    controller VARCHAR(255),
    power_rating VARCHAR(100),
    
    -- Dates
    installation_date DATE,
    commissioning_date DATE,
    warranty_expiry_date DATE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'operational',
    -- Status: operational, shutdown, maintenance, decommissioned
    
    operational_hours INTEGER DEFAULT 0,
    
    -- Health & Maintenance
    health_score INTEGER DEFAULT 100,
    last_maintenance_date TIMESTAMP,
    next_maintenance_date TIMESTAMP,
    maintenance_frequency_days INTEGER,
    
    -- Cost
    purchase_cost DECIMAL(10, 2),
    annual_maintenance_cost DECIMAL(10, 2),
    
    -- Location within facility
    floor VARCHAR(50),
    room VARCHAR(50),
    location_notes TEXT,
    
    -- Images & Documents
    primary_image_url TEXT,
    
    -- Metadata
    notes TEXT,
    custom_fields JSONB DEFAULT '{}',
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_equipment_facility ON equipment(facility_id);
CREATE INDEX idx_equipment_type ON equipment(equipment_type);
CREATE INDEX idx_equipment_status ON equipment(status);
CREATE INDEX idx_equipment_next_maintenance ON equipment(next_maintenance_date);
CREATE INDEX idx_equipment_health ON equipment(health_score);
```

### equipment_images

```sql
CREATE TABLE equipment_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    caption VARCHAR(255),
    is_primary BOOLEAN DEFAULT FALSE,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_equipment_images_equipment ON equipment_images(equipment_id);
```

### equipment_documents

```sql
CREATE TABLE equipment_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    document_type VARCHAR(100),
    -- Types: manual, warranty, certificate, inspection_report, etc.
    
    title VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    file_size_kb INTEGER,
    file_type VARCHAR(50),
    
    expiry_date DATE,
    
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_equipment_documents_equipment ON equipment_documents(equipment_id);
CREATE INDEX idx_equipment_documents_expiry ON equipment_documents(expiry_date);
```

### tasks

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    facility_id UUID REFERENCES facilities(id) ON DELETE CASCADE,
    
    -- Task Info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    task_type VARCHAR(100) DEFAULT 'maintenance',
    -- Types: maintenance, repair, inspection, installation, emergency
    
    -- Priority & Status
    priority VARCHAR(50) DEFAULT 'medium',
    -- Priority: low, medium, high, critical
    
    status VARCHAR(50) DEFAULT 'new',
    -- Status: new, assigned, in_progress, on_hold, completed, canceled, rejected
    
    -- Assignment
    assigned_to UUID REFERENCES users(id),
    assigned_team_id UUID REFERENCES teams(id),
    
    -- Scheduling
    scheduled_date TIMESTAMP,
    due_date TIMESTAMP,
    estimated_hours DECIMAL(5, 2),
    
    -- Completion
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    actual_hours DECIMAL(5, 2),
    
    -- Work details
    work_performed TEXT,
    parts_used TEXT,
    
    -- Service Request Link
    service_request_id UUID,
    
    -- Metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tasks_equipment ON tasks(equipment_id);
CREATE INDEX idx_tasks_facility ON tasks(facility_id);
CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_scheduled_date ON tasks(scheduled_date);
```

### task_comments

```sql
CREATE TABLE task_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_task_comments_task ON task_comments(task_id);
```

### task_attachments

```sql
CREATE TABLE task_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    file_size_kb INTEGER,
    file_type VARCHAR(50),
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_task_attachments_task ON task_attachments(task_id);
```

### task_history

```sql
CREATE TABLE task_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    -- Actions: created, assigned, status_changed, priority_changed, completed, etc.
    
    old_value TEXT,
    new_value TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_task_history_task ON task_history(task_id);
CREATE INDEX idx_task_history_created ON task_history(created_at);
```

### maintenance_schedules

```sql
CREATE TABLE maintenance_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE CASCADE,
    
    schedule_name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Frequency
    frequency_type VARCHAR(50) NOT NULL,
    -- Types: daily, weekly, monthly, quarterly, yearly, custom_days
    
    frequency_value INTEGER,
    -- For custom_days: number of days between maintenance
    
    -- Scheduling
    last_run_date TIMESTAMP,
    next_run_date TIMESTAMP NOT NULL,
    
    -- Task Template
    task_title VARCHAR(255),
    task_description TEXT,
    task_priority VARCHAR(50) DEFAULT 'medium',
    estimated_hours DECIMAL(5, 2),
    
    -- Assignment
    default_assigned_to UUID REFERENCES users(id),
    default_assigned_team UUID REFERENCES teams(id),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_maintenance_schedules_equipment ON maintenance_schedules(equipment_id);
CREATE INDEX idx_maintenance_schedules_next_run ON maintenance_schedules(next_run_date);
CREATE INDEX idx_maintenance_schedules_active ON maintenance_schedules(is_active);
```

### service_requests

```sql
CREATE TABLE service_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request Info
    request_number VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    service_type VARCHAR(100),
    
    -- Location
    facility_id UUID REFERENCES facilities(id),
    equipment_id UUID REFERENCES equipment(id),
    
    -- Priority & Status
    priority VARCHAR(50) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'pending',
    -- Status: pending, approved, rejected, converted_to_task
    
    -- Requester (Customer)
    requested_by UUID REFERENCES users(id),
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    -- Response
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    
    -- Conversion
    converted_task_id UUID REFERENCES tasks(id),
    converted_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_service_requests_status ON service_requests(status);
CREATE INDEX idx_service_requests_facility ON service_requests(facility_id);
CREATE INDEX idx_service_requests_requested_by ON service_requests(requested_by);
```

### technician_work_logs

```sql
CREATE TABLE technician_work_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    technician_id UUID NOT NULL REFERENCES users(id),
    
    -- Status
    work_status VARCHAR(50) NOT NULL,
    -- Status: open, in_progress, on_hold, completed
    
    -- Location Tracking
    arrival_latitude DECIMAL(10, 8),
    arrival_longitude DECIMAL(11, 8),
    arrival_time TIMESTAMP,
    
    departure_latitude DECIMAL(10, 8),
    departure_longitude DECIMAL(11, 8),
    departure_time TIMESTAMP,
    
    -- Time Tracking
    travel_time_minutes INTEGER,
    work_time_minutes INTEGER,
    lunch_break_minutes INTEGER DEFAULT 0,
    
    -- Work Details
    work_notes TEXT,
    signature_url TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_work_logs_task ON technician_work_logs(task_id);
CREATE INDEX idx_work_logs_technician ON technician_work_logs(technician_id);
CREATE INDEX idx_work_logs_arrival ON technician_work_logs(arrival_time);
```

### inventory_parts

```sql
CREATE TABLE inventory_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Part Info
    part_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    
    -- Specifications
    manufacturer VARCHAR(255),
    model VARCHAR(255),
    specifications JSONB DEFAULT '{}',
    
    -- Pricing
    unit_price DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Stock
    quantity_in_stock INTEGER DEFAULT 0,
    reorder_level INTEGER DEFAULT 10,
    reorder_quantity INTEGER DEFAULT 50,
    
    -- Location
    warehouse_location VARCHAR(100),
    
    -- Supplier
    supplier_name VARCHAR(255),
    supplier_contact VARCHAR(255),
    supplier_part_number VARCHAR(100),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inventory_parts_category ON inventory_parts(category);
CREATE INDEX idx_inventory_parts_stock ON inventory_parts(quantity_in_stock);
```

### inventory_transactions

```sql
CREATE TABLE inventory_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id UUID NOT NULL REFERENCES inventory_parts(id) ON DELETE CASCADE,
    
    transaction_type VARCHAR(50) NOT NULL,
    -- Types: purchase, usage, adjustment, return
    
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2),
    total_cost DECIMAL(10, 2),
    
    -- Reference
    task_id UUID REFERENCES tasks(id),
    purchase_order_id UUID,
    
    notes TEXT,
    
    performed_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inventory_transactions_part ON inventory_transactions(part_id);
CREATE INDEX idx_inventory_transactions_task ON inventory_transactions(task_id);
CREATE INDEX idx_inventory_transactions_type ON inventory_transactions(transaction_type);
```

### notifications

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    notification_type VARCHAR(100) NOT NULL,
    -- Types: task_assigned, task_due, equipment_alert, etc.
    
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    -- Links
    link_url TEXT,
    link_type VARCHAR(50),
    link_id UUID,
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at);
```

### push_subscriptions

```sql
CREATE TABLE push_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    endpoint TEXT NOT NULL,
    p256dh_key TEXT NOT NULL,
    auth_key TEXT NOT NULL,
    
    user_agent TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_push_subscriptions_user ON push_subscriptions(user_id);
```

### audit_logs

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    
    action VARCHAR(100) NOT NULL,
    -- Actions: create, update, delete, login, logout, etc.
    
    resource_type VARCHAR(100),
    -- Types: equipment, task, user, facility, etc.
    
    resource_id UUID,
    
    ip_address INET,
    user_agent TEXT,
    
    changes JSONB,
    -- Store before/after values
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

## Indexes Strategy

### Performance Indexes

```sql
-- Composite indexes for common queries
CREATE INDEX idx_tasks_assigned_status ON tasks(assigned_to, status);
CREATE INDEX idx_tasks_facility_status ON tasks(facility_id, status);
CREATE INDEX idx_equipment_facility_status ON equipment(facility_id, status);

-- Partial indexes for active records
CREATE INDEX idx_active_equipment ON equipment(id) WHERE status = 'operational';
CREATE INDEX idx_active_schedules ON maintenance_schedules(id) WHERE is_active = TRUE;

-- Full-text search indexes
CREATE INDEX idx_equipment_search ON equipment USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '')));
CREATE INDEX idx_tasks_search ON tasks USING gin(to_tsvector('english', title || ' ' || COALESCE(description, '')));
```

## Data Retention Policies

```sql
-- Archive old completed tasks (older than 2 years)
CREATE TABLE tasks_archive (LIKE tasks INCLUDING ALL);

-- Archive old audit logs (older than 1 year)
CREATE TABLE audit_logs_archive (LIKE audit_logs INCLUDING ALL);

-- Scheduled job to move old data
-- Run monthly via Celery Beat
```

## Database Migrations Strategy

```bash
# Create new tenant schema
python manage.py create_tenant \
  --schema_name=tenant_newclient \
  --name="New Client Inc" \
  --domain=newclient.fieldpilot.com

# Run migrations on all tenant schemas
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

# Backup before migrations
pg_dump -Fc fieldpilot_db > backup_$(date +%Y%m%d).dump
```

## Performance Considerations

### Connection Pooling

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': 'fieldpilot_db',
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

### Query Optimization

```python
# Use select_related for foreign keys
equipment = Equipment.objects.select_related(
    'facility', 'building', 'created_by'
).get(id=equipment_id)

# Use prefetch_related for reverse relations
facility = Facility.objects.prefetch_related(
    'equipment_set', 'tasks_set'
).get(id=facility_id)

# Use only() to fetch specific fields
equipment_list = Equipment.objects.only(
    'id', 'name', 'status', 'health_score'
).filter(facility_id=facility_id)
```

## Backup & Recovery

```bash
# Daily automated backups
pg_dump -Fc -h localhost -U postgres fieldpilot_db > \
  /backups/fieldpilot_$(date +%Y%m%d_%H%M%S).dump

# Point-in-time recovery setup
# Enable WAL archiving in postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /archive/%f'

# Restore from backup
pg_restore -d fieldpilot_db backup_20251029.dump
```
