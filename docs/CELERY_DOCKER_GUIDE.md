# Celery with Docker - Complete Guide

## Overview

FieldRino uses Celery for asynchronous task processing and scheduled jobs. All Celery services run in Docker containers for easy deployment and scaling.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Services                           │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Django     │────▶│    Redis     │◀────│   Celery     │
│     Web      │     │   (Broker)   │     │   Worker     │
│  Port: 8000  │     │  Port: 6379  │     │              │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            ▲
                            │
                     ┌──────┴───────┐
                     │              │
              ┌──────────────┐ ┌──────────────┐
              │   Celery     │ │   Flower     │
              │    Beat      │ │ (Monitoring) │
              │ (Scheduler)  │ │  Port: 5555  │
              └──────────────┘ └──────────────┘
```

## Services

| Service | Purpose | Port |
|---------|---------|------|
| **web** | Django application | 8000 |
| **celery-worker** | Processes async tasks | - |
| **celery-beat** | Runs scheduled tasks | - |
| **flower** | Celery monitoring UI | 5555 |
| **redis** | Message broker | 6379 |
| **postgres** | Database | 5432 |

## Quick Start

### 1. Start All Services

```bash
# Using management script (recommended)
./docker-manage.sh start

# Or using docker-compose
docker-compose up -d
```

### 2. Check Status

```bash
./docker-manage.sh status

# Expected output:
# fieldrino_web             Up
# fieldrino_celery_worker   Up
# fieldrino_celery_beat     Up
# fieldrino_flower          Up
# fieldrino_redis           Up
# fieldrino_postgres        Up
```

### 3. Access Services

| Service | URL |
|---------|-----|
| Django API | http://localhost:8000 |
| Flower (Monitoring) | http://localhost:5555 |
| CloudBeaver (Database) | http://localhost:8978 |
| MailHog (Email Testing) | http://localhost:8025 |

## Scheduled Tasks

These tasks run automatically via Celery Beat:

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_subscription_renewals` | Daily 2:00 AM | Process trial conversions and renewals |
| `retry_failed_payments` | Daily 3:00 AM | Retry failed payment attempts |
| `send_renewal_reminders` | Daily 9:00 AM | Send renewal reminder emails |
| `update_all_usage_counts` | Daily 12:00 AM | Update subscription usage metrics |

## Management Script

The `docker-manage.sh` script simplifies common operations:

```bash
# Service Management
./docker-manage.sh start              # Start all services
./docker-manage.sh stop               # Stop all services
./docker-manage.sh restart [service]  # Restart specific service
./docker-manage.sh status             # Show service status

# Logs
./docker-manage.sh logs               # View all logs
./docker-manage.sh logs celery-worker # View specific service logs

# Django Commands
./docker-manage.sh django migrate     # Run migrations
./docker-manage.sh django createsuperuser  # Create superuser
./docker-manage.sh django-shell       # Open Django shell

# Celery Commands
./docker-manage.sh celery inspect active  # Check active tasks
./docker-manage.sh celery status          # Worker status

# Scaling
./docker-manage.sh scale 3            # Scale to 3 workers

# Shell Access
./docker-manage.sh shell web          # Open bash in container
./docker-manage.sh shell celery-worker

# Maintenance
./docker-manage.sh build              # Rebuild containers
./docker-manage.sh cleanup            # Remove all containers

# Help
./docker-manage.sh help               # Show all commands
```

## Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat

# Using script
./docker-manage.sh logs celery-worker
```

### Restart Services

```bash
# After code changes
docker-compose restart celery-worker

# After schedule changes
docker-compose restart celery-beat

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

### Scale Workers

```bash
# Run 3 worker instances
docker-compose up -d --scale celery-worker=3

# Using script
./docker-manage.sh scale 3
```

## Monitoring with Flower

1. Open http://localhost:5555
2. View:
   - **Tasks**: Active, scheduled, completed tasks
   - **Workers**: Worker status and performance
   - **Broker**: Redis connection and queue status
   - **Monitor**: Real-time execution graphs

## Development Workflow

### Code Changes

```bash
# Django code - auto-reloads (no restart needed)
# Just save the file

# Celery task code - restart worker
docker-compose restart celery-worker

# Celery schedule - restart beat
docker-compose restart celery-beat
```

### Testing Tasks

```bash
# Open Django shell
docker-compose exec web python manage.py shell

# Test a task
>>> from apps.billing.tasks import process_subscription_renewals
>>> result = process_subscription_renewals.delay()
>>> result.get()  # Wait for result

# Or run synchronously
>>> process_subscription_renewals()
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

## Configuration

### Environment Variables (.env)

```bash
# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Database
DATABASE_URL=postgresql://fieldrino_user:fieldrino_password@postgres:5432/fieldrino_db
```

### Celery Settings (config/celery.py)

```python
# Celery Beat Schedule
app.conf.beat_schedule = {
    'process-subscription-renewals': {
        'task': 'apps.billing.tasks.process_subscription_renewals',
        'schedule': crontab(hour=2, minute=0),
    },
    # ... more tasks
}
```

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

### Worker Not Processing Tasks

```bash
# Check worker logs
docker-compose logs celery-worker

# Check Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG

# Restart worker
docker-compose restart celery-worker
```

### Beat Not Running Scheduled Tasks

```bash
# Check beat logs
docker-compose logs celery-beat

# Restart beat
docker-compose restart celery-beat

# Verify schedule
docker-compose exec web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.all()
```

### Tasks Stuck in Queue

```bash
# Check queue length
docker-compose exec redis redis-cli
> LLEN celery

# Purge all tasks (careful!)
docker-compose exec web celery -A config purge
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

## Production Deployment

### Recommended Configuration

```yaml
# docker-compose.prod.yml
celery-worker:
  command: celery -A config worker -l warning --concurrency=4
  deploy:
    replicas: 2
    resources:
      limits:
        cpus: '1'
        memory: 512M
  restart: always

celery-beat:
  command: celery -A config beat -l warning
  deploy:
    replicas: 1  # Only one beat instance!
  restart: always
```

### Health Checks

```yaml
celery-worker:
  healthcheck:
    test: ["CMD-SHELL", "celery -A config inspect ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

## Task Development

### Creating a New Task

```python
# apps/billing/tasks.py
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def my_new_task(self, param1, param2):
    """
    Description of what this task does.
    """
    try:
        # Task logic here
        logger.info(f"Processing task with {param1}, {param2}")
        
        # Do work
        result = process_something(param1, param2)
        
        return result
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

### Scheduling a Task

```python
# config/celery.py
app.conf.beat_schedule = {
    'my-new-task': {
        'task': 'apps.billing.tasks.my_new_task',
        'schedule': crontab(hour=10, minute=30),  # 10:30 AM daily
        'args': ('param1', 'param2'),
    },
}
```

## Best Practices

1. **Single Beat Instance**: Only run ONE celery-beat instance
2. **Multiple Workers**: Scale workers based on load
3. **Task Timeouts**: Set appropriate time limits
4. **Error Handling**: Use try-except in tasks
5. **Idempotency**: Make tasks idempotent (safe to retry)
6. **Monitoring**: Use Flower in production
7. **Logging**: Log task execution for debugging
8. **Resource Limits**: Set memory/CPU limits in production

## Stopping Services

```bash
# Stop all services
docker-compose down

# Or using script
./docker-manage.sh stop

# Stop and remove volumes (deletes data!)
docker-compose down -v

# Stop specific service
docker-compose stop celery-worker
```

## Related Files

- `Dockerfile` - Container image definition
- `docker-compose.yml` - Service orchestration
- `config/celery.py` - Celery configuration
- `config/__init__.py` - Celery app initialization
- `apps/billing/tasks.py` - Task definitions
- `requirements.txt` - Python dependencies
- `docker-manage.sh` - Management script

## Support

For issues:
1. Check logs: `./docker-manage.sh logs`
2. Check Flower: http://localhost:5555
3. Check service status: `./docker-manage.sh status`
4. Review task code in `apps/billing/tasks.py`
5. Check Celery config in `config/celery.py`
