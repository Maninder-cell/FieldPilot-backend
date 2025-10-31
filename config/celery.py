"""
Celery Configuration

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')

app = Celery('fieldpilot')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Automated recurring tasks
app.conf.beat_schedule = {
    # Process subscription renewals daily at 2 AM
    'process-subscription-renewals': {
        'task': 'apps.billing.tasks.process_subscription_renewals',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
    },
    
    # Retry failed payments daily at 3 AM
    'retry-failed-payments': {
        'task': 'apps.billing.tasks.retry_failed_payments',
        'schedule': crontab(hour=3, minute=0),  # 3:00 AM daily
    },
    
    # Send renewal reminders daily at 9 AM
    'send-renewal-reminders': {
        'task': 'apps.billing.tasks.send_renewal_reminders',
        'schedule': crontab(hour=9, minute=0),  # 9:00 AM daily
    },
    
    # Update usage counts daily at midnight
    'update-usage-counts': {
        'task': 'apps.billing.tasks.update_all_usage_counts',
        'schedule': crontab(hour=0, minute=0),  # Midnight daily
    },
}

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f'Request: {self.request!r}')
