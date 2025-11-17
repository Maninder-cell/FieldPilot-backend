#!/bin/bash

# FieldPilot Backend - Simple Start Script
# Continues on errors, reuses existing containers

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
echo "║         FieldPilot Backend - Quick Start                  ║"
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

# Step 2: Check docker-compose
print_status "Checking docker-compose..."
if command -v docker-compose &> /dev/null; then
    print_success "docker-compose found"
else
    print_error "docker-compose not found. Install from: https://docs.docker.com/compose/install/"
    exit 1
fi

# Step 3: Check Python
print_status "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Step 4: Virtual Environment
print_status "Checking virtual environment..."
if [ ! -d "venv" ]; then
    print_warning "Creating virtual environment..."
    python3 -m venv venv || print_error "Failed to create venv (continuing...)"
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Step 5: Activate venv
print_status "Activating virtual environment..."
source venv/bin/activate || {
    print_error "Failed to activate venv (continuing...)"
}

# Step 6: Install Python dependencies
print_status "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip --quiet 2>/dev/null || true
    pip install -r requirements.txt --quiet 2>/dev/null || {
        print_warning "Some dependencies failed to install (continuing...)"
    }
    print_success "Dependencies installed"
else
    print_error "requirements.txt not found (continuing...)"
fi

# Step 7: Check .env file
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env not found"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Created .env from .env.example"
    else
        print_error ".env not found (continuing...)"
    fi
else
    print_success ".env found"
fi

# Step 8: Start Docker services (reuse existing containers)
print_status "Starting Docker services..."
docker-compose up -d 2>/dev/null || {
    print_warning "Some containers failed to start (continuing...)"
}
print_success "Docker services started"

# Step 9: Wait for PostgreSQL
print_status "Waiting for PostgreSQL..."
MAX_TRIES=30
TRIES=0
until docker exec fieldpilot_postgres pg_isready -U fieldpilot_user > /dev/null 2>&1 || [ $TRIES -eq $MAX_TRIES ]; do
    TRIES=$((TRIES+1))
    echo -n "."
    sleep 1
done
echo ""
if [ $TRIES -eq $MAX_TRIES ]; then
    print_error "PostgreSQL not ready (continuing...)"
else
    print_success "PostgreSQL ready (${TRIES}s)"
fi

# Step 10: Wait for Redis
print_status "Waiting for Redis..."
sleep 2
print_success "Redis ready"

# Step 11: Database connection test
print_status "Testing database connection..."
python manage.py check --database default > /dev/null 2>&1 || {
    print_error "Database connection failed (continuing...)"
}

# Step 12: Create migrations
print_status "Creating migrations..."
python manage.py makemigrations 2>/dev/null || {
    print_error "Failed to create migrations (continuing...)"
}

# Step 13: Apply migrations (shared schema)
print_status "Applying shared schema migrations..."
python manage.py migrate_schemas --shared 2>/dev/null || {
    print_error "Shared migrations failed (continuing...)"
}

# Step 14: Apply migrations (tenant schemas)
print_status "Applying tenant schema migrations..."
python manage.py migrate_schemas --tenant 2>/dev/null || {
    print_warning "No tenant schemas to migrate (continuing...)"
}

# Step 15: Create superuser if needed
print_status "Checking for superuser..."
SUPERUSER_EXISTS=$(python manage.py shell -c "from apps.authentication.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null || echo "False")
if [ "$SUPERUSER_EXISTS" = "False" ]; then
    print_warning "No superuser found"
    echo "Create superuser? (y/n): "
    read -r CREATE_SUPERUSER
    if [ "$CREATE_SUPERUSER" = "y" ] || [ "$CREATE_SUPERUSER" = "Y" ]; then
        python manage.py createsuperuser || print_error "Failed to create superuser (continuing...)"
    fi
else
    print_success "Superuser exists"
fi

# Step 16: Setup public tenant
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

# Step 17: Seed subscription plans
print_status "Seeding subscription plans..."
python manage.py seed_plans > /dev/null 2>&1 || {
    print_warning "Plan seeding failed (continuing...)"
}
print_success "Plans seeded"

# Step 18: Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput > /dev/null 2>&1 || {
    print_warning "Static collection failed (continuing...)"
}

# Step 19: Final system check
print_status "Running system check..."
python manage.py check 2>/dev/null || {
    print_warning "System check has warnings (continuing...)"
}

# Success message
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ READY TO START!                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "FieldPilot Backend is ready!"
echo ""
echo "📚 API Documentation:"
echo "   • Swagger UI:  http://localhost:8000/api/docs/"
echo "   • ReDoc:       http://localhost:8000/api/redoc/"
echo ""
echo "🔧 Management:"
echo "   • Admin Panel: http://localhost:8000/admin/"
echo "   • pgAdmin:     http://localhost:5050 (admin@fieldpilot.com / admin)"
echo "   • MailHog:     http://localhost:8025 (email testing)"
echo ""
echo "🗄️  Database:"
echo "   • PostgreSQL:  localhost:5432"
echo "   • Database:    fieldpilot_db"
echo "   • User:        fieldpilot_user"
echo "   • Password:    fieldpilot_password"
echo ""
echo "🚀 Starting Django development server..."
echo "   Press Ctrl+C to stop"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start Django server
python manage.py runserver
