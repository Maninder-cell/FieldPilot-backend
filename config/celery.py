"""
Celery Configuration

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')

app = Celery('fieldrino')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Automated recurring tasks
# Note: Subscription renewals, payments, and invoicing are now fully managed by Stripe.
# Stripe automatically handles renewals, retries, and dunning via webhooks.
app.conf.beat_schedule = {
    # Update usage counts daily at midnight
    # This is still needed for local usage tracking (not managed by Stripe)
    'update-usage-counts': {
        'task': 'apps.billing.tasks.update_all_usage_counts',
        'schedule': crontab(hour=0, minute=0),  # Midnight daily
    },
    
    # Sync subscriptions from Stripe every 6 hours (backup to webhooks)
    # This ensures local data stays in sync even if webhook events are missed
    'sync-subscriptions-from-stripe': {
        'task': 'apps.billing.tasks.sync_subscriptions_from_stripe',
        'schedule': crontab(hour='*/6', minute=0),  # Every 6 hours
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
