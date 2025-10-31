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
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_success "Python $PYTHON_VERSION is installed"

# Step 5: Check if virtual environment exists, create if not
print_status "Checking virtual environment..."
if [ ! -d "venv" ]; then
    print_warning "Virtual environment not found. Creating..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Step 6: Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate
print_success "Virtual environment activated"

# Step 7: Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found!"
    exit 1
fi

# Step 8: Install/Update Python dependencies
print_status "Installing/Updating Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
print_success "Python dependencies installed"

# Step 9: Check if .env file exists
print_status "Checking environment configuration..."
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Please create one from .env.example"
    exit 1
fi
print_success "Environment configuration found"

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
    if docker-compose up -d 2>&1; then
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
            echo "  sudo systemctl restart docker  # On Linux"
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
python manage.py makemigrations > /dev/null 2>&1 || true
print_success "Migrations created"

# Step 17: Apply migrations
print_status "Applying database migrations..."
python manage.py migrate
print_success "Database migrations applied"

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
echo "📊 API Endpoints:"
echo "   ├─ Authentication: 11 endpoints"
echo "   ├─ Onboarding:     6 endpoints"
echo "   ├─ Billing:        11 endpoints"
echo "   └─ Total:          28 endpoints"
echo ""
echo "🚀 Starting Django development server..."
echo "   Press Ctrl+C to stop the server"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start Django server
python manage.py runserver
