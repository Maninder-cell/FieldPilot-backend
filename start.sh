#!/bin/bash

# FieldPilot Backend - Automated Setup & Start Script
# This script will set up everything needed to run the project

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show progress for long-running commands
show_progress() {
    local pid=$1
    local message=$2
    local spin='-\|/'
    local i=0
    
    echo -n "   $message "
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) %4 ))
        printf "\r   $message ${spin:$i:1}"
        sleep 0.1
    done
    printf "\r   $message ✓\n"
}

# Print banner
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         FieldPilot Backend - Automated Setup              ║"
echo "║              Production-Ready API Platform                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check if Docker is installed
print_status "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker is installed"

# Step 2: Check if Docker is running
print_status "Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi
print_success "Docker is running"

# Step 3: Check if docker-compose is installed
print_status "Checking docker-compose installation..."
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install docker-compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi
print_success "docker-compose is installed"

# Step 4: Check if Python 3 is installed
print_status "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or higher."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "On macOS, install with: brew install python3"
    fi
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python $PYTHON_VERSION is installed"

# Check if pip is available
if ! python3 -m pip --version &> /dev/null; then
    print_warning "pip is not available, installing..."
    python3 -m ensurepip --upgrade || {
        print_error "Failed to install pip"
        exit 1
    }
fi

# Step 5: Check if virtual environment exists, create if not
print_status "Checking virtual environment..."
if [ ! -d "venv" ]; then
    print_warning "Virtual environment not found. Creating..."
    echo "   This may take a minute..."
    python3 -m venv venv || {
        print_error "Failed to create virtual environment"
        echo "Try running: python3 -m pip install --upgrade pip setuptools"
        exit 1
    }
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Step 6: Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate || {
    print_error "Failed to activate virtual environment"
    echo "Try running: source venv/bin/activate"
    exit 1
}
print_success "Virtual environment activated"

# Step 7: Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found!"
    exit 1
fi

# Step 8: Install/Update Python dependencies
print_status "Installing/Updating Python dependencies (this may take a few minutes)..."

# Check if requirements have changed
REQUIREMENTS_HASH=""
if [ -f ".requirements_hash" ]; then
    REQUIREMENTS_HASH=$(cat .requirements_hash)
fi
CURRENT_HASH=$(md5sum requirements.txt 2>/dev/null || md5 requirements.txt 2>/dev/null | awk '{print $1}')

if [ "$REQUIREMENTS_HASH" = "$CURRENT_HASH" ]; then
    print_success "Dependencies are up to date (skipping installation)"
else
    echo "   Upgrading pip..."
    pip install --upgrade pip --quiet || pip install --upgrade pip
    
    echo "   Installing requirements (showing progress)..."
    echo "   This may take 2-5 minutes on first run..."
    pip install -r requirements.txt || {
        print_error "Failed to install dependencies"
        echo ""
        echo "Try running manually:"
        echo "  source venv/bin/activate"
        echo "  pip install -r requirements.txt"
        exit 1
    }
    
    # Save hash to skip next time
    echo "$CURRENT_HASH" > .requirements_hash
    print_success "Python dependencies installed"
fi

# Step 9: Check if .env file exists
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found."
    if [ -f ".env.example" ]; then
        echo "Would you like to create .env from .env.example? (y/n)"
        read -r CREATE_ENV
        if [ "$CREATE_ENV" = "y" ] || [ "$CREATE_ENV" = "Y" ]; then
            cp .env.example .env
            print_success ".env file created from .env.example"
            print_warning "Please edit .env file with your configuration before continuing"
            exit 0
        else
            print_error "Cannot continue without .env file"
            exit 1
        fi
    else
        print_error ".env file not found. Please create one."
        exit 1
    fi
fi
print_success "Environment configuration found"

# Step 9.5: Detect which settings file to use
print_status "Detecting Django settings..."
if grep -q "DJANGO_SETTINGS_MODULE" .env 2>/dev/null; then
    SETTINGS_MODULE=$(grep "DJANGO_SETTINGS_MODULE" .env | cut -d'=' -f2 | tr -d ' "'"'"'')
    print_success "Using settings: $SETTINGS_MODULE"
else
    print_warning "DJANGO_SETTINGS_MODULE not set in .env, using default (config.settings_dev)"
    export DJANGO_SETTINGS_MODULE=config.settings_dev
fi

# Step 10: Check for port conflicts
print_status "Checking for port conflicts..."

# Check if port 5432 (PostgreSQL) is in use
if lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    print_warning "Port 5432 (PostgreSQL) is already in use"
    echo "Would you like to stop the process using this port? (y/n)"
    read -r STOP_POSTGRES
    if [ "$STOP_POSTGRES" = "y" ] || [ "$STOP_POSTGRES" = "Y" ]; then
        print_status "Stopping process on port 5432..."
        lsof -ti:5432 | xargs kill -9 2>/dev/null || true
        sleep 2
        print_success "Port 5432 freed"
    else
        print_error "Cannot start PostgreSQL. Port 5432 is in use."
        exit 1
    fi
fi

# Check if port 6379 (Redis) is in use
if lsof -Pi :6379 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    print_warning "Port 6379 (Redis) is already in use"
    echo "Would you like to stop the process using this port? (y/n)"
    read -r STOP_REDIS
    if [ "$STOP_REDIS" = "y" ] || [ "$STOP_REDIS" = "Y" ]; then
        print_status "Stopping process on port 6379..."
        lsof -ti:6379 | xargs kill -9 2>/dev/null || true
        sleep 2
        print_success "Port 6379 freed"
    else
        print_error "Cannot start Redis. Port 6379 is in use."
        exit 1
    fi
fi

# Check if port 5050 (pgAdmin) is in use
if lsof -Pi :5050 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    print_warning "Port 5050 (pgAdmin) is already in use"
    print_status "Stopping process on port 5050..."
    lsof -ti:5050 | xargs kill -9 2>/dev/null || true
    sleep 1
    print_success "Port 5050 freed"
fi

print_success "No port conflicts"

# Step 11: Clean up Docker completely
print_status "Cleaning up Docker containers and networks..."
docker-compose down --remove-orphans > /dev/null 2>&1 || true
docker network prune -f > /dev/null 2>&1 || true
sleep 2
print_success "Docker cleanup complete"

# Step 12: Start Docker services
print_status "Starting Docker services (PostgreSQL, Redis, pgAdmin)..."
MAX_RETRIES=3
RETRY=0

while [ $RETRY -lt $MAX_RETRIES ]; do
    if docker-compose up -d; then
        print_success "Docker services started"
        break
    else
        RETRY=$((RETRY+1))
        if [ $RETRY -lt $MAX_RETRIES ]; then
            print_warning "Failed to start services. Retrying ($RETRY/$MAX_RETRIES)..."
            docker-compose down --remove-orphans > /dev/null 2>&1 || true
            sleep 3
        else
            print_error "Failed to start Docker services after $MAX_RETRIES attempts"
            echo ""
            echo "The port is likely held by a zombie Docker process."
            echo "Run these commands manually:"
            echo ""
            echo "  docker-compose down -v"
            echo "  docker network prune -f"
            echo "  docker system prune -f"
            echo "  # On Linux: sudo systemctl restart docker"
            echo "  # On macOS: Restart Docker Desktop"
            echo ""
            echo "Then run ./start.sh again"
            exit 1
        fi
    fi
done

# Step 13: Wait for PostgreSQL to be ready
print_status "Waiting for PostgreSQL to be ready (this may take 30-60 seconds)..."
MAX_TRIES=60
TRIES=0
until docker exec fieldpilot_postgres pg_isready -U fieldpilot_user > /dev/null 2>&1 || [ $TRIES -eq $MAX_TRIES ]; do
    TRIES=$((TRIES+1))
    if [ $((TRIES % 10)) -eq 0 ]; then
        echo -n " ${TRIES}s"
    else
        echo -n "."
    fi
    sleep 1
done
echo ""

if [ $TRIES -eq $MAX_TRIES ]; then
    print_error "PostgreSQL failed to start after 60 seconds"
    echo "Check logs: docker-compose logs postgres"
    exit 1
fi
print_success "PostgreSQL is ready (took ${TRIES}s)"

# Step 14: Wait for Redis to be ready
print_status "Waiting for Redis to be ready..."
sleep 3
print_success "Redis is ready"

# Step 15: Check database connection
print_status "Testing database connection..."
if python manage.py check --database default > /dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Database connection failed"
    exit 1
fi

# Step 16: Create migrations if needed
print_status "Creating database migrations..."
MIGRATION_OUTPUT=$(python manage.py makemigrations 2>&1)
if echo "$MIGRATION_OUTPUT" | grep -q "No changes detected"; then
    print_success "No new migrations needed"
else
    echo "$MIGRATION_OUTPUT"
    print_success "Migrations created"
fi

# Step 17: Apply migrations (Multi-tenant setup)
print_status "Applying database migrations for shared schema..."
python manage.py migrate_schemas --shared
print_success "Shared schema migrations applied"

print_status "Applying database migrations for tenant schemas..."
python manage.py migrate_schemas --tenant 2>/dev/null || print_warning "No tenant schemas to migrate yet"
print_success "Tenant schema migrations applied"

# Step 18: Check if superuser exists
print_status "Checking for superuser..."
SUPERUSER_EXISTS=$(python manage.py shell -c "from apps.authentication.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null || echo "False")

if [ "$SUPERUSER_EXISTS" = "False" ]; then
    print_warning "No superuser found."
    echo ""
    echo "Would you like to create a superuser now? (y/n)"
    read -r CREATE_SUPERUSER
    if [ "$CREATE_SUPERUSER" = "y" ] || [ "$CREATE_SUPERUSER" = "Y" ]; then
        python manage.py createsuperuser
    else
        print_warning "Skipping superuser creation. You can create one later with: python manage.py createsuperuser"
    fi
else
    print_success "Superuser exists"
fi

# Step 18.5: Setup default tenant if none exists
print_status "Checking for default tenant..."
TENANT_EXISTS=$(python manage.py shell -c "from apps.tenants.models import Tenant; print(Tenant.objects.exclude(schema_name='public').exists())" 2>/dev/null || echo "False")

if [ "$TENANT_EXISTS" = "False" ]; then
    print_warning "No tenant found. Creating public schema for onboarding..."
    echo "   Creating public tenant..."
    python manage.py shell <<'EOF'
from apps.tenants.models import Tenant, Domain

# Create public tenant (for onboarding/registration)
public_tenant = Tenant.objects.create(
    schema_name="public",
    name="Public",
    slug="public"
)

# Map localhost to public schema for onboarding
# Note: django-tenants uses hostname WITHOUT port
Domain.objects.create(domain="localhost", tenant=public_tenant, is_primary=True)
Domain.objects.create(domain="127.0.0.1", tenant=public_tenant, is_primary=False)
Domain.objects.create(domain="public.localhost", tenant=public_tenant, is_primary=False)

print(f"   ✓ Created public tenant")
print(f"   ✓ Domains: localhost, 127.0.0.1, public.localhost")
print(f"   ✓ Use localhost:8000 for registration and company creation")
EOF
    
    print_success "Public tenant created and configured"
else
    print_success "Tenant(s) exist"
    
    # Ensure public tenant has correct domains
    python manage.py shell <<'EOF' 2>/dev/null || true
from apps.tenants.models import Tenant, Domain

# Get or create public tenant
public_tenant, created = Tenant.objects.get_or_create(
    schema_name='public',
    defaults={
        'name': 'Public',
        'slug': 'public'
    }
)

# Ensure localhost points to public
Domain.objects.get_or_create(
    domain='localhost',
    defaults={'tenant': public_tenant, 'is_primary': True}
)
Domain.objects.get_or_create(
    domain='127.0.0.1',
    defaults={'tenant': public_tenant, 'is_primary': False}
)

print("   ✓ Verified public tenant configuration")
EOF
fi

# Step 19: Seed subscription plans
print_status "Seeding subscription plans..."
python manage.py seed_plans > /dev/null 2>&1 || true
print_success "Subscription plans seeded"

# Step 20: Collect static files (if needed)
print_status "Collecting static files..."
python manage.py collectstatic --noinput > /dev/null 2>&1 || true
print_success "Static files collected"

# Step 21: Final system check
print_status "Running final system check..."
if python manage.py check; then
    print_success "System check passed"
else
    print_error "System check failed"
    exit 1
fi

# Step 22: Display tenant information
print_status "Fetching tenant information..."
python manage.py shell <<'EOF' 2>/dev/null || true
from apps.tenants.models import Tenant, Domain

tenants = Tenant.objects.exclude(schema_name='public')
if tenants.exists():
    print("\n📋 Available Tenants:")
    for tenant in tenants:
        domains = tenant.domains.all()
        print(f"\n   • {tenant.name} (schema: {tenant.schema_name})")
        if domains:
            for domain in domains:
                primary = "⭐" if domain.is_primary else "  "
                print(f"     {primary} http://{domain.domain}")
        else:
            print(f"     ⚠️  No domains configured")
EOF
print_success "Tenant information displayed"

# Print success message and access information
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETE!                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_success "FieldPilot Backend is ready to use!"
echo ""
echo "📚 API Documentation:"
echo "   ├─ Swagger UI:  http://127.0.0.1:8000/api/docs/"
echo "   ├─ ReDoc:       http://127.0.0.1:8000/api/redoc/"
echo "   └─ OpenAPI:     http://127.0.0.1:8000/api/schema/"
echo ""
echo "🔧 Management Tools:"
echo "   ├─ Admin Panel: http://127.0.0.1:8000/admin/"
echo "   └─ pgAdmin:     http://localhost:5050"
echo "                   (admin@fieldpilot.com / admin)"
echo ""
echo "🗄️  Database:"
echo "   ├─ PostgreSQL:  localhost:5432"
echo "   ├─ Database:    fieldpilot_db"
echo "   ├─ Username:    fieldpilot_user"
echo "   └─ Password:    fieldpilot_password"
echo ""
echo "🏢 Multi-Tenancy:"
echo "   ├─ Default Tenant:  http://localhost:8000"
echo "   ├─ Tenant Access:   http://{tenant}.localhost:8000"
echo "   └─ Create Tenant:   Via API or Django admin"
echo ""
echo "📊 API Endpoints:"
echo "   ├─ Authentication:  /api/v1/auth/"
echo "   ├─ Tenants:         /api/v1/onboarding/"
echo "   ├─ Billing:         /api/v1/billing/"
echo "   ├─ Customers:       /api/v1/customers/"
echo "   ├─ Facilities:      /api/v1/facilities/"
echo "   ├─ Buildings:       /api/v1/buildings/"
echo "   ├─ Equipment:       /api/v1/equipment/"
echo "   └─ Tasks:           /api/v1/tasks/"
echo ""
echo "� Userful Commands:"
echo "   ├─ Create tenant:       python manage.py shell"
echo "   ├─ Run migrations:      python manage.py migrate_schemas --tenant"
echo "   ├─ Create superuser:    python manage.py createsuperuser"
echo "   ├─ Seed plans:          python manage.py seed_plans"
echo "   └─ Django shell:        python manage.py shell"
echo ""
echo "📖 Documentation:"
echo "   ├─ Quick Start:         docs/QUICK_START.md"
echo "   ├─ Customer Invites:    docs/CUSTOMER_INVITATION_FLOW.md"
echo "   └─ CORS Setup:          docs/CORS_AND_ENVIRONMENT_SETUP.md"
echo ""
echo "🚀 Starting Django development server..."
echo "   Press Ctrl+C to stop the server"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start Django server
python manage.py runserver
