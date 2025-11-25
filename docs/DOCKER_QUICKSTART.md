# Docker Quick Start Guide

## Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)
- `.env` file configured (copy from `.env.example`)

## Quick Start

### 1. Start All Services

```bash
# Using docker-compose directly
docker-compose up -d

# Or using the management script
./docker-manage.sh start
```

This starts:
- ✅ PostgreSQL database
- ✅ Redis (message broker)
- ✅ Django web application
- ✅ Celery worker (async tasks)
- ✅ Celery beat (scheduler)
- ✅ Flower (monitoring)
- ✅ CloudBeaver (database UI)
- ✅ MailHog (email testing)

### 2. Check Status

```bash
docker-compose ps

# Or
./docker-manage.sh status
```

### 3. Access Services

| Service | URL | Description |
|---------|-----|-------------|
| **Django API** | http://localhost:8000 | Main application |
| **Flower** | http://localhost:5555 | Celery task monitoring |
| **CloudBeaver** | http://localhost:8978 | Database management |
| **MailHog** | http://localhost:8025 | Email testing UI |

### 4. Run Migrations

```bash
# First time setup
docker-compose exec web python manage.py migrate

# Or using the script
./docker-manage.sh django migrate
```

### 5. Create Superuser

```bash
docker-compose exec web python manage.py createsuperuser

# Or
./docker-manage.sh django createsuperuser
```

### 6. Seed Data

```bash
# Seed subscription plans
docker-compose exec web python manage.py seed_plans

# Or
./docker-manage.sh django seed_plans
```

## Management Script

The `docker-manage.sh` script simplifies common operations:

```bash
# Start services
./docker-manage.sh start

# Stop services
./docker-manage.sh stop

# View logs
./docker-manage.sh logs
./docker-manage.sh logs celery-worker

# Restart a service
./docker-manage.sh restart celery-worker

# Django commands
./docker-manage.sh django migrate
./docker-manage.sh django createsuperuser
./docker-manage.sh django shell

# Celery commands
./docker-manage.sh celery inspect active
./docker-manage.sh celery status

# Scale workers
./docker-manage.sh scale 3

# Open shell
./docker-manage.sh shell web
./docker-manage.sh django-shell

# Show help
./docker-manage.sh help
```

## Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker
docker-compose logs -f web

# Using script
./docker-manage.sh logs celery-worker
```

### Restart Services

```bash
# Restart specific service
docker-compose restart celery-worker

# Restart all
docker-compose restart

# Using script
./docker-manage.sh restart celery-worker
```

### Execute Commands

```bash
# Django shell
docker-compose exec web python manage.py shell

# Bash shell
docker-compose exec web /bin/bash

# Using script
./docker-manage.sh django-shell
./docker-manage.sh shell web
```

### Database Operations

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create migration
docker-compose exec web python manage.py makemigrations

# Access PostgreSQL
docker-compose exec postgres psql -U fieldrino_user -d fieldrino_db

# Or use CloudBeaver UI at http://localhost:8978
```

### Celery Operations

```bash
# Check active tasks
docker-compose exec web celery -A config inspect active

# Check scheduled tasks
docker-compose exec web celery -A config inspect scheduled

# Purge all tasks
docker-compose exec web celery -A config purge

# Using script
./docker-manage.sh celery inspect active
```

## Development Workflow

### 1. Code Changes

When you make code changes:

```bash
# Django code changes - auto-reload (no restart needed)
# Just save the file

# Celery code changes - restart worker
docker-compose restart celery-worker

# Settings changes - restart all
docker-compose restart
```

### 2. Database Changes

```bash
# Create migration
./docker-manage.sh django makemigrations

# Apply migration
./docker-manage.sh django migrate

# Or run both
./docker-manage.sh django makemigrations && ./docker-manage.sh django migrate
```

### 3. Install New Package

```bash
# Add to requirements.txt
echo "new-package==1.0.0" >> requirements.txt

# Rebuild containers
docker-compose build

# Restart services
docker-compose up -d
```

### 4. Testing

```bash
# Run tests
docker-compose exec web pytest

# Run specific test
docker-compose exec web pytest apps/billing/tests/

# With coverage
docker-compose exec web pytest --cov=apps
```

## Monitoring

### Flower (Celery Monitoring)

1. Open http://localhost:5555
2. View:
   - Active tasks
   - Completed tasks
   - Failed tasks
   - Worker status
   - Task execution times

### CloudBeaver (Database)

1. Open http://localhost:8978
2. First time setup:
   - Username: `admin`
   - Password: `admin`
3. Add connection:
   - Host: `postgres`
   - Port: `5432`
   - Database: `fieldrino_db`
   - Username: `fieldrino_user`
   - Password: `fieldrino_password`

### MailHog (Email Testing)

1. Open http://localhost:8025
2. View all emails sent by the application
3. Test email templates and content

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs postgres
docker-compose logs redis

# Restart services
docker-compose restart
```

### Database Connection Error

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Celery Tasks Not Running

```bash
# Check worker logs
docker-compose logs celery-worker

# Check beat logs
docker-compose logs celery-beat

# Check Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Restart Celery services
docker-compose restart celery-worker celery-beat
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Out of Disk Space

```bash
# Remove unused containers
docker system prune

# Remove unused volumes
docker volume prune

# Remove everything (careful!)
docker system prune -a --volumes
```

## Stopping Services

### Stop All Services

```bash
docker-compose down

# Or
./docker-manage.sh stop
```

### Stop and Remove Volumes

```bash
# This will delete all data!
docker-compose down -v
```

### Stop Specific Service

```bash
docker-compose stop celery-worker
```

## Production Deployment

For production, use a separate compose file:

```bash
# Create docker-compose.prod.yml
# Then run:
docker-compose -f docker-compose.prod.yml up -d
```

Key differences for production:
- Use environment-specific settings
- Set proper resource limits
- Use production-grade web server (Gunicorn)
- Enable SSL/TLS
- Set up proper logging
- Use secrets management
- Enable health checks

## Environment Variables

Required in `.env` file:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://fieldrino_user:fieldrino_password@postgres:5432/fieldrino_db

# Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Stripe (optional)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025
```

## Next Steps

1. ✅ Start services: `./docker-manage.sh start`
2. ✅ Run migrations: `./docker-manage.sh django migrate`
3. ✅ Create superuser: `./docker-manage.sh django createsuperuser`
4. ✅ Seed plans: `./docker-manage.sh django seed_plans`
5. ✅ Access API: http://localhost:8000
6. ✅ Monitor Celery: http://localhost:5555

## Documentation

- `docs/CELERY_DOCKER_GUIDE.md` - Complete Celery guide
- `docs/FREE_TRIAL_PAYMENT_FLOW.md` - Payment flow details
- `docs/API_COMPLETE_FLOW.md` - API documentation

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Flower Documentation](https://flower.readthedocs.io/)

## Support

For issues:
1. Check logs: `./docker-manage.sh logs`
2. Check status: `./docker-manage.sh status`
3. Review documentation in `docs/`
4. Check Docker and Docker Compose versions
