# FieldPilot - Development Guide

## Getting Started

This guide will help you set up the FieldPilot development environment and understand the development workflow.

## Prerequisites

### Required Software

- **Python 3.11+**
- **Node.js 20+** and npm/yarn
- **PostgreSQL 15+**
- **Redis 7+**
- **Docker & Docker Compose** (recommended)
- **Git**

### Recommended Tools

- **VS Code** with extensions:
  - Python
  - Pylance
  - ESLint
  - Prettier
  - Tailwind CSS IntelliSense
- **Postman** or **Insomnia** for API testing
- **pgAdmin** or **DBeaver** for database management

## Project Setup

### Option 1: Docker Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/fieldpilot.git
cd fieldpilot

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate_schemas --shared
docker-compose exec backend python manage.py migrate_schemas --tenant

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Admin Panel: http://localhost:8000/admin
```

### Option 2: Manual Setup

#### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements/development.txt

# Copy environment file
cp .env.example .env

# Edit .env with your database credentials
nano .env

# Create database
createdb fieldpilot_db

# Run migrations
python manage.py migrate_schemas --shared
python manage.py migrate_schemas --tenant

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
# or
yarn install

# Copy environment file
cp .env.example .env.local

# Edit .env.local with API URL
nano .env.local

# Start development server
npm run dev
# or
yarn dev
```

#### Redis Setup

```bash
# Install Redis (Ubuntu/Debian)
sudo apt-get install redis-server

# Start Redis
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

#### Celery Workers

```bash
cd backend

# Start Celery worker
celery -A config worker -l info

# Start Celery Beat (scheduler)
celery -A config beat -l info

# Or use one command for both
celery -A config worker -B -l info
```

## Environment Variables

### Backend (.env)

```bash
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/fieldpilot_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# AWS S3 (for file storage)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=fieldpilot-dev
AWS_S3_REGION_NAME=us-east-1

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# JWT
JWT_ACCESS_TOKEN_LIFETIME=15  # minutes
JWT_REFRESH_TOKEN_LIFETIME=7  # days

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Sentry (optional)
SENTRY_DSN=https://...
```

### Frontend (.env.local)

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Google Maps (optional)
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your-api-key

# Environment
NEXT_PUBLIC_ENV=development
```

## Development Workflow

### Creating a New Feature

1. **Create a new branch**
```bash
git checkout -b feature/equipment-qr-scanning
```

2. **Backend Development**
```bash
cd backend

# Create new app if needed
python manage.py startapp qr_scanning

# Add to INSTALLED_APPS in settings.py
# Create models, serializers, views
# Write tests
python manage.py test apps.qr_scanning

# Create migrations
python manage.py makemigrations
python manage.py migrate_schemas --tenant
```

3. **Frontend Development**
```bash
cd frontend

# Create components
mkdir -p components/qr-scanner
touch components/qr-scanner/QRScanner.tsx

# Create API hooks
touch lib/api/qr-scanning.ts

# Write tests
npm run test
```

4. **Test the feature**
```bash
# Run backend tests
cd backend
python manage.py test

# Run frontend tests
cd frontend
npm run test

# Manual testing
# Test in browser at http://localhost:3000
```

5. **Commit and push**
```bash
git add .
git commit -m "feat: add QR code scanning for equipment"
git push origin feature/equipment-qr-scanning
```

6. **Create Pull Request**
- Go to GitHub
- Create PR from your branch to `develop`
- Request code review
- Address feedback
- Merge when approved

## Code Style & Standards

### Python (Backend)

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Lint with flake8
flake8 .

# Type checking with mypy
mypy .

# Run all checks
./scripts/lint.sh
```

**Code Style Guidelines:**
- Follow PEP 8
- Use type hints
- Write docstrings for all functions/classes
- Keep functions small and focused
- Use meaningful variable names

```python
# Good example
def calculate_equipment_health_score(
    equipment: Equipment,
    maintenance_history: List[MaintenanceRecord]
) -> int:
    """
    Calculate health score for equipment based on maintenance history.
    
    Args:
        equipment: Equipment instance
        maintenance_history: List of maintenance records
        
    Returns:
        Health score between 0-100
    """
    # Implementation
    pass
```

### TypeScript (Frontend)

```bash
# Format code with Prettier
npm run format

# Lint with ESLint
npm run lint

# Type check
npm run type-check
```

**Code Style Guidelines:**
- Use TypeScript for all new code
- Define interfaces for all data structures
- Use functional components with hooks
- Keep components small and reusable
- Use Tailwind CSS for styling

```typescript
// Good example
interface Equipment {
  id: string;
  name: string;
  status: 'operational' | 'maintenance' | 'shutdown';
  healthScore: number;
}

interface EquipmentCardProps {
  equipment: Equipment;
  onSelect: (id: string) => void;
}

export const EquipmentCard: React.FC<EquipmentCardProps> = ({
  equipment,
  onSelect
}) => {
  return (
    <div className="rounded-lg border p-4 hover:shadow-lg transition-shadow">
      <h3 className="text-lg font-semibold">{equipment.name}</h3>
      <p className="text-sm text-gray-600">Status: {equipment.status}</p>
      <button onClick={() => onSelect(equipment.id)}>View Details</button>
    </div>
  );
};
```

## Testing

### Backend Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.equipment

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# Run specific test
python manage.py test apps.equipment.tests.test_models.EquipmentModelTest
```

**Test Structure:**
```python
from django.test import TestCase
from apps.equipment.models import Equipment

class EquipmentModelTest(TestCase):
    def setUp(self):
        self.equipment = Equipment.objects.create(
            name="Test Equipment",
            equipment_type="HVAC"
        )
    
    def test_equipment_creation(self):
        self.assertEqual(self.equipment.name, "Test Equipment")
        self.assertIsNotNone(self.equipment.equipment_number)
    
    def test_health_score_default(self):
        self.assertEqual(self.equipment.health_score, 100)
```

### Frontend Testing

```bash
# Run all tests
npm run test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch

# Run specific test file
npm run test -- EquipmentCard.test.tsx
```

**Test Structure:**
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { EquipmentCard } from './EquipmentCard';

describe('EquipmentCard', () => {
  const mockEquipment = {
    id: '123',
    name: 'Test Equipment',
    status: 'operational' as const,
    healthScore: 85
  };

  it('renders equipment name', () => {
    render(<EquipmentCard equipment={mockEquipment} onSelect={jest.fn()} />);
    expect(screen.getByText('Test Equipment')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', () => {
    const onSelect = jest.fn();
    render(<EquipmentCard equipment={mockEquipment} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByText('View Details'));
    expect(onSelect).toHaveBeenCalledWith('123');
  });
});
```

## Database Management

### Creating Migrations

```bash
# Create migrations for all apps
python manage.py makemigrations

# Create migration for specific app
python manage.py makemigrations equipment

# Create empty migration (for data migrations)
python manage.py makemigrations --empty equipment
```

### Running Migrations

```bash
# Migrate shared schema (public)
python manage.py migrate_schemas --shared

# Migrate all tenant schemas
python manage.py migrate_schemas --tenant

# Migrate specific tenant
python manage.py migrate_schemas --schema=tenant_acme_corp
```

### Creating a Tenant

```bash
# Using management command
python manage.py create_tenant \
  --schema_name=tenant_testcorp \
  --name="Test Corp" \
  --domain=testcorp.localhost:8000

# Or using Django shell
python manage.py shell

from apps.tenants.models import Tenant, Domain

tenant = Tenant.objects.create(
    schema_name='tenant_testcorp',
    name='Test Corp',
    slug='testcorp'
)

Domain.objects.create(
    tenant=tenant,
    domain='testcorp.localhost:8000',
    is_primary=True
)
```

### Database Backup & Restore

```bash
# Backup
pg_dump -Fc fieldpilot_db > backup_$(date +%Y%m%d).dump

# Restore
pg_restore -d fieldpilot_db backup_20251029.dump

# Backup specific schema
pg_dump -n tenant_acme_corp fieldpilot_db > tenant_backup.sql
```

## Debugging

### Backend Debugging

```python
# Use Django Debug Toolbar (already installed in dev)
# Access at http://localhost:8000/__debug__/

# Use pdb for debugging
import pdb; pdb.set_trace()

# Or use ipdb (better interface)
import ipdb; ipdb.set_trace()

# Print SQL queries
from django.db import connection
print(connection.queries)
```

### Frontend Debugging

```typescript
// Use React DevTools browser extension

// Console logging
console.log('Equipment data:', equipment);

// Debugger
debugger;

// React Query DevTools (already configured)
// Shows in bottom-right corner in development
```

### Celery Debugging

```bash
# Run Celery with debug logging
celery -A config worker -l debug

# Test task manually
python manage.py shell

from apps.maintenance.tasks import create_scheduled_maintenance_tasks
result = create_scheduled_maintenance_tasks.delay()
print(result.get())
```

## Common Tasks

### Adding a New API Endpoint

1. **Create serializer** (`serializers.py`):
```python
from rest_framework import serializers
from .models import Equipment

class EquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipment
        fields = '__all__'
```

2. **Create view** (`views.py`):
```python
from rest_framework import viewsets
from .models import Equipment
from .serializers import EquipmentSerializer

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated]
```

3. **Register URL** (`urls.py`):
```python
from rest_framework.routers import DefaultRouter
from .views import EquipmentViewSet

router = DefaultRouter()
router.register(r'equipment', EquipmentViewSet)

urlpatterns = router.urls
```

### Adding a Celery Task

```python
# apps/maintenance/tasks.py
from celery import shared_task
from .models import MaintenanceSchedule

@shared_task
def create_scheduled_maintenance_tasks():
    """Create tasks for due maintenance schedules."""
    schedules = MaintenanceSchedule.objects.filter(
        is_active=True,
        next_run_date__lte=timezone.now()
    )
    
    for schedule in schedules:
        # Create task
        Task.objects.create(
            equipment=schedule.equipment,
            title=schedule.task_title,
            # ... other fields
        )
        
        # Update next run date
        schedule.next_run_date = calculate_next_run_date(schedule)
        schedule.save()
    
    return f"Created {schedules.count()} tasks"
```

### Adding a Frontend Page

```typescript
// app/(dashboard)/equipment/[id]/page.tsx
import { EquipmentDetails } from '@/components/equipment/EquipmentDetails';

interface PageProps {
  params: {
    id: string;
  };
}

export default async function EquipmentPage({ params }: PageProps) {
  return (
    <div className="container mx-auto py-8">
      <EquipmentDetails equipmentId={params.id} />
    </div>
  );
}
```

## Performance Optimization

### Backend Optimization

```python
# Use select_related for foreign keys
equipment = Equipment.objects.select_related(
    'facility', 'building'
).get(id=equipment_id)

# Use prefetch_related for reverse relations
facilities = Facility.objects.prefetch_related(
    'equipment_set', 'tasks_set'
).all()

# Use only() to fetch specific fields
equipment_list = Equipment.objects.only(
    'id', 'name', 'status'
).filter(facility_id=facility_id)

# Use database indexes
class Equipment(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['facility_id', 'status']),
        ]

# Cache expensive queries
from django.core.cache import cache

def get_equipment_stats(facility_id):
    cache_key = f'equipment_stats_{facility_id}'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = calculate_stats(facility_id)
        cache.set(cache_key, stats, 300)  # 5 minutes
    
    return stats
```

### Frontend Optimization

```typescript
// Use React Query for caching
import { useQuery } from '@tanstack/react-query';

export function useEquipment(id: string) {
  return useQuery({
    queryKey: ['equipment', id],
    queryFn: () => fetchEquipment(id),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Lazy load components
import dynamic from 'next/dynamic';

const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <p>Loading...</p>,
});

// Optimize images
import Image from 'next/image';

<Image
  src="/equipment.jpg"
  alt="Equipment"
  width={500}
  height={300}
  priority
/>
```

## Troubleshooting

### Common Issues

**Issue: Migrations not applying to tenant schemas**
```bash
# Solution: Run tenant migrations explicitly
python manage.py migrate_schemas --tenant
```

**Issue: CORS errors in development**
```python
# Solution: Add to settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

**Issue: Celery tasks not running**
```bash
# Solution: Check Redis connection
redis-cli ping

# Restart Celery worker
celery -A config worker -l info
```

**Issue: Next.js build errors**
```bash
# Solution: Clear cache and rebuild
rm -rf .next
npm run build
```

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment instructions.

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Celery Documentation](https://docs.celeryproject.org/)
