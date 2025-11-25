#!/bin/bash

# FieldRino Docker Management Script
# Simplifies common Docker Compose operations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

# Check if docker-compose is installed
check_docker() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose is not installed"
        exit 1
    fi
}

# Start all services
start_all() {
    print_info "Starting all services..."
    docker-compose up -d
    print_success "All services started"
    print_info "Access points:"
    echo "  - Django Web: http://localhost:8000"
    echo "  - Flower (Celery): http://localhost:5555"
    echo "  - CloudBeaver (DB): http://localhost:8978"
    echo "  - MailHog: http://localhost:8025"
}

# Stop all services
stop_all() {
    print_info "Stopping all services..."
    docker-compose down
    print_success "All services stopped"
}

# Restart specific service
restart_service() {
    if [ -z "$1" ]; then
        print_error "Please specify a service name"
        echo "Available services: web, celery-worker, celery-beat, flower, postgres, redis"
        exit 1
    fi
    print_info "Restarting $1..."
    docker-compose restart "$1"
    print_success "$1 restarted"
}

# View logs
view_logs() {
    if [ -z "$1" ]; then
        print_info "Showing logs for all services..."
        docker-compose logs -f
    else
        print_info "Showing logs for $1..."
        docker-compose logs -f "$1"
    fi
}

# Check service status
check_status() {
    print_info "Service status:"
    docker-compose ps
}

# Execute Django command
django_command() {
    if [ -z "$1" ]; then
        print_error "Please specify a Django command"
        exit 1
    fi
    print_info "Executing: python manage.py $*"
    docker-compose exec web python manage.py "$@"
}

# Execute Celery command
celery_command() {
    if [ -z "$1" ]; then
        print_error "Please specify a Celery command"
        exit 1
    fi
    print_info "Executing: celery -A config $*"
    docker-compose exec web celery -A config "$@"
}

# Shell access
shell_access() {
    service="${1:-web}"
    print_info "Opening shell in $service..."
    docker-compose exec "$service" /bin/bash
}

# Django shell
django_shell() {
    print_info "Opening Django shell..."
    docker-compose exec web python manage.py shell
}

# Build containers
build_containers() {
    print_info "Building containers..."
    docker-compose build
    print_success "Containers built"
}

# Clean up
cleanup() {
    print_warning "This will remove all containers, volumes, and images"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."
        docker-compose down -v --rmi all
        print_success "Cleanup complete"
    else
        print_info "Cleanup cancelled"
    fi
}

# Scale workers
scale_workers() {
    count="${1:-2}"
    print_info "Scaling celery workers to $count instances..."
    docker-compose up -d --scale celery-worker="$count"
    print_success "Workers scaled to $count"
}

# Show help
show_help() {
    cat << EOF
${GREEN}FieldRino Docker Management Script${NC}

${YELLOW}Usage:${NC}
  ./docker-manage.sh [command] [options]

${YELLOW}Commands:${NC}
  ${BLUE}start${NC}              Start all services
  ${BLUE}stop${NC}               Stop all services
  ${BLUE}restart [service]${NC}  Restart a specific service
  ${BLUE}status${NC}             Show service status
  ${BLUE}logs [service]${NC}     View logs (all or specific service)
  ${BLUE}build${NC}              Build/rebuild containers
  ${BLUE}shell [service]${NC}    Open bash shell in container (default: web)
  ${BLUE}django-shell${NC}       Open Django shell
  ${BLUE}django [command]${NC}   Execute Django management command
  ${BLUE}celery [command]${NC}   Execute Celery command
  ${BLUE}scale [count]${NC}      Scale celery workers (default: 2)
  ${BLUE}cleanup${NC}            Remove all containers, volumes, and images
  ${BLUE}help${NC}               Show this help message

${YELLOW}Examples:${NC}
  ./docker-manage.sh start
  ./docker-manage.sh logs celery-worker
  ./docker-manage.sh restart celery-beat
  ./docker-manage.sh django migrate
  ./docker-manage.sh celery inspect active
  ./docker-manage.sh scale 3
  ./docker-manage.sh shell web

${YELLOW}Services:${NC}
  - web              Django application
  - celery-worker    Celery worker
  - celery-beat      Celery beat scheduler
  - flower           Celery monitoring
  - postgres         PostgreSQL database
  - redis            Redis cache/broker
  - cloudbeaver      Database management UI
  - mailhog          Email testing

${YELLOW}Access Points:${NC}
  - Django:      http://localhost:8000
  - Flower:      http://localhost:5555
  - CloudBeaver: http://localhost:8978
  - MailHog:     http://localhost:8025

EOF
}

# Main script
check_docker

case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_service "$2"
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs "$2"
        ;;
    build)
        build_containers
        ;;
    shell)
        shell_access "$2"
        ;;
    django-shell)
        django_shell
        ;;
    django)
        shift
        django_command "$@"
        ;;
    celery)
        shift
        celery_command "$@"
        ;;
    scale)
        scale_workers "$2"
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run './docker-manage.sh help' for usage information"
        exit 1
        ;;
esac
