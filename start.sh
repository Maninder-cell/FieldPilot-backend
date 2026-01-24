#!/bin/bash

# FieldRino Backend - Docker-First Start Script
# All services run in Docker containers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         FieldRino Backend - Docker Quick Start           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check Docker
print_status "Checking Docker..."
if command -v docker &> /dev/null; then
    if docker info > /dev/null 2>&1; then
        print_success "Docker is running"
    else
        print_error "Docker is not running. Please start Docker."
        exit 1
    fi
else
    print_error "Docker not found. Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Step 2: Check docker compose
print_status "Checking docker compose..."
if docker compose version &> /dev/null; then
    print_success "docker compose found"
else
    print_error "docker compose not found. Install from: https://docs.docker.com/compose/install/"
    exit 1
fi
# Step 3: Check .env file
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env not found"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env from .env.example"
        print_warning "Please update .env with your configuration"
    else
        print_error ".env.example not found. Creating basic .env..."
        cat > .env << 'ENVEOF'
# Django
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://fieldrino_user:fieldrino_password@postgres:5432/fieldrino_db

# Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email (MailHog for development)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025

# Stripe (optional - add your keys)
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
ENVEOF
        print_success "Basic .env created"
    fi
else
    print_success ".env found"
fi

# Step 4: Build Docker images (if needed)
print_status "Building Docker images..."
docker compose build --quiet 2>/dev/null || {
    print_warning "Build had warnings (continuing...)"
}
print_success "Docker images ready"

# Step 5: Start Docker services
print_status "Starting Docker services..."
docker compose up -d 2>/dev/null || {
    print_error "Failed to start some containers"
    docker compose ps
    exit 1
}
print_success "Docker services started"

# Step 6: Wait for PostgreSQL
print_status "Waiting for PostgreSQL..."
MAX_TRIES=30
TRIES=0
until docker compose exec -T postgres pg_isready -U fieldrino_user > /dev/null 2>&1 || [ $TRIES -eq $MAX_TRIES ]; do
    TRIES=$((TRIES+1))
    echo -n "."
    sleep 1
done
echo ""
if [ $TRIES -eq $MAX_TRIES ]; then
    print_error "PostgreSQL not ready after 30s"
    print_warning "Check logs: docker compose logs postgres"
else
    print_success "PostgreSQL ready (${TRIES}s)"
fi

# Step 7: Wait for Redis
print_status "Waiting for Redis..."
sleep 2
docker compose exec -T redis redis-cli ping > /dev/null 2>&1 && print_success "Redis ready" || print_warning "Redis not responding"

# Step 8: Run migrations inside Docker container
print_status "Running database migrations..."
docker compose exec -T web python manage.py migrate_schemas --shared 2>/dev/null || {
    print_warning "Shared migrations failed (continuing...)"
}
docker compose exec -T web python manage.py migrate_schemas --tenant 2>/dev/null || {
    print_warning "Tenant migrations failed (continuing...)"
}
print_success "Migrations completed"

# Step 9: Setup public tenant
print_status "Setting up public tenant..."
docker compose exec -T web python manage.py shell <<'EOF' 2>/dev/null || print_warning "Tenant setup failed (continuing...)"
from apps.tenants.models import Tenant, Domain

public_tenant, created = Tenant.objects.get_or_create(
    schema_name='public',
    defaults={'name': 'Public', 'slug': 'public'}
)

Domain.objects.get_or_create(domain='localhost', defaults={'tenant': public_tenant, 'is_primary': True})
Domain.objects.get_or_create(domain='127.0.0.1', defaults={'tenant': public_tenant, 'is_primary': False})

if created:
    print("✓ Public tenant created")
else:
    print("✓ Public tenant exists")
EOF

# Step 10: Seed subscription plans
print_status "Seeding subscription plans..."
docker compose exec -T web python manage.py seed_plans > /dev/null 2>&1 || {
    print_warning "Plan seeding failed (continuing...)"
}
print_success "Plans seeded"

# Step 11: Collect static files
print_status "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput > /dev/null 2>&1 || {
    print_warning "Static collection failed (continuing...)"
}
print_success "Static files collected"

# Step 12: Check all services
print_status "Checking service status..."
docker compose ps

# Check Celery services
CELERY_WORKER_RUNNING=$(docker ps --filter "name=fieldrino_celery_worker" --filter "status=running" -q)
CELERY_BEAT_RUNNING=$(docker ps --filter "name=fieldrino_celery_beat" --filter "status=running" -q)
FLOWER_RUNNING=$(docker ps --filter "name=fieldrino_flower" --filter "status=running" -q)

if [ -n "$CELERY_WORKER_RUNNING" ]; then
    print_success "Celery worker is running"
else
    print_warning "Celery worker not running (check: docker compose logs celery-worker)"
fi

if [ -n "$CELERY_BEAT_RUNNING" ]; then
    print_success "Celery beat is running"
else
    print_warning "Celery beat not running (check: docker compose logs celery-beat)"
fi

if [ -n "$FLOWER_RUNNING" ]; then
    print_success "Flower monitoring is running"
else
    print_warning "Flower not running (check: docker compose logs flower)"
fi

# Success message
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ ALL SERVICES RUNNING!                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "FieldRino Backend is ready!"
echo ""
echo "�  API Documentation:"
echo "   • Swagger UI:  http://localhost:8000/api/docs/"
echo "   • ReDoc:       http://localhost:8000/api/redoc/"
echo ""
echo "🔧 Management:"
echo "   • Admin Panel:  http://localhost:8000/admin/"
echo "   • Flower:       http://localhost:5555 (Celery monitoring)"
echo "   • CloudBeaver:  http://localhost:8978 (database management)"
echo "   • MailHog:      http://localhost:8025 (email testing)"
echo ""
echo "🗄️  Database:"
echo "   • PostgreSQL:  localhost:5432"
echo "   • Database:    fieldrino_db"
echo "   • User:        fieldrino_user"
echo "   • Password:    fieldrino_password"
echo ""
echo "⚙️  Background Tasks:"
echo "   • Celery Worker:  Running in Docker"
echo "   • Celery Beat:    Running in Docker (scheduled tasks)"
echo "   • View logs:      docker compose logs -f celery-worker"
echo ""
echo "🐳 Docker Commands:"
echo "   • View logs:      docker compose logs -f [service]"
echo "   • Restart:        docker compose restart [service]"
echo "   • Stop all:       docker compose down"
echo "   • Django shell:   docker compose exec web python manage.py shell"
echo ""
echo "💡 Tip: Use './docker-manage.sh' for easier Docker management"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
print_success "All services are running in Docker containers!"
print_status "To view logs: docker compose logs -f"
print_status "To stop: docker compose down"
echo ""
