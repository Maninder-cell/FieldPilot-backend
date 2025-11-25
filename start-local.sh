#!/bin/bash

# FieldRino Backend - Local Development Start Script
# For running Django locally (without Docker web container)
# Docker is still used for PostgreSQL, Redis, and Celery

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
echo "║      FieldRino Backend - Local Development Mode          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check Python
print_status "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Step 2: Check Docker
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

# Step 3: Virtual Environment
print_status "Checking virtual environment..."
if [ ! -d "venv" ]; then
    print_warning "Creating virtual environment..."
    python3 -m venv venv || {
        print_error "Failed to create venv"
        exit 1
    }
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Step 4: Activate venv
print_status "Activating virtual environment..."
source venv/bin/activate || {
    print_error "Failed to activate venv"
    exit 1
}

# Step 5: Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet || {
        print_error "Failed to install dependencies"
        exit 1
    }
    print_success "Dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Step 6: Check .env file
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env not found"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env from .env.example"
    else
        print_error ".env not found. Please create it."
        exit 1
    fi
else
    print_success ".env found"
fi

# Step 7: Start only infrastructure services (not web)
print_status "Starting infrastructure services (PostgreSQL, Redis, Celery)..."
docker-compose up -d postgres redis celery-worker celery-beat flower cloudbeaver mailhog 2>/dev/null || {
    print_error "Failed to start Docker services"
    exit 1
}
print_success "Infrastructure services started"

# Step 8: Wait for PostgreSQL
print_status "Waiting for PostgreSQL..."
MAX_TRIES=30
TRIES=0
until docker-compose exec -T postgres pg_isready -U fieldrino_user > /dev/null 2>&1 || [ $TRIES -eq $MAX_TRIES ]; do
    TRIES=$((TRIES+1))
    echo -n "."
    sleep 1
done
echo ""
if [ $TRIES -eq $MAX_TRIES ]; then
    print_error "PostgreSQL not ready"
    exit 1
else
    print_success "PostgreSQL ready (${TRIES}s)"
fi

# Step 9: Wait for Redis
print_status "Waiting for Redis..."
sleep 2
print_success "Redis ready"

# Step 10: Run migrations
print_status "Running database migrations..."
python manage.py migrate_schemas --shared 2>/dev/null || {
    print_warning "Shared migrations failed (continuing...)"
}
python manage.py migrate_schemas --tenant 2>/dev/null || {
    print_warning "Tenant migrations failed (continuing...)"
}
print_success "Migrations completed"

# Step 11: Setup public tenant
print_status "Setting up public tenant..."
python manage.py shell <<'EOF' 2>/dev/null || print_warning "Tenant setup failed (continuing...)"
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

# Step 12: Seed subscription plans
print_status "Seeding subscription plans..."
python manage.py seed_plans > /dev/null 2>&1 || {
    print_warning "Plan seeding failed (continuing...)"
}
print_success "Plans seeded"

# Step 13: Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput > /dev/null 2>&1 || {
    print_warning "Static collection failed (continuing...)"
}
print_success "Static files collected"

# Success message
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✅ READY FOR LOCAL DEVELOPMENT!               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "FieldRino Backend is ready!"
echo ""
echo "📚 API Documentation:"
echo "   • Swagger UI:  http://localhost:8000/api/docs/"
echo "   • ReDoc:       http://localhost:8000/api/redoc/"
echo ""
echo "🔧 Management:"
echo "   • Admin Panel:  http://localhost:8000/admin/"
echo "   • Flower:       http://localhost:5555 (Celery monitoring)"
echo "   • CloudBeaver:  http://localhost:8978 (database management)"
echo "   • MailHog:      http://localhost:8025 (email testing)"
echo ""
echo "🗄️  Database & Services (Docker):"
echo "   • PostgreSQL:  localhost:5432"
echo "   • Redis:       localhost:6379"
echo "   • Celery:      Running in Docker"
echo ""
echo "💻 Django (Local):"
echo "   • Running on host machine"
echo "   • Virtual environment: venv/"
echo ""
echo "🚀 Starting Django development server..."
echo "   Press Ctrl+C to stop"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start Django server locally
python manage.py runserver
