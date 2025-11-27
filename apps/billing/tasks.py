"""
Billing Celery Tasks

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.

Note: Subscription renewals, payments, and invoicing are now fully managed by Stripe.
Stripe automatically handles:
- Subscription renewals
- Payment processing
- Invoice generation
- Failed payment retries
- Dunning management

Webhooks keep local subscription status synchronized.
"""
from celery import shared_task
from django.utils import timezone
import logging

from .models import Subscription

logger = logging.getLogger(__name__)


@shared_task
def update_all_usage_counts():
    """
    Update usage counts for all active subscriptions.
    Runs daily to track resource usage for plan limit enforcement.
    
    This is the only billing task still needed since usage tracking
    is local (not managed by Stripe).
    """
    logger.info("Updating usage counts for all subscriptions...")
    
    active_subscriptions = Subscription.objects.filter(
        status__in=['active', 'trialing']
    )
    
    updated_count = 0
    failed_count = 0
    
    for subscription in active_subscriptions:
        try:
            subscription.update_usage_counts()
            updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update usage for subscription {subscription.id}: {str(e)}")
            failed_count += 1
    
    logger.info(f"Updated usage counts for {updated_count} subscriptions ({failed_count} failed)")
    return {
        'updated': updated_count,
        'failed': failed_count
    }


@shared_task
def sync_subscriptions_from_stripe():
    """
    Sync all subscription statuses from Stripe.
    Runs periodically to ensure local data is in sync with Stripe.
    
    This is a backup to webhooks in case any webhook events are missed.
    """
    logger.info("Syncing subscriptions from Stripe...")
    
    subscriptions = Subscription.objects.filter(
        status__in=['active', 'trialing', 'past_due']
    )
    
    synced_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        try:
            subscription.sync_from_stripe()
            synced_count += 1
        except Exception as e:
            logger.error(f"Failed to sync subscription {subscription.id}: {str(e)}")
            failed_count += 1
    
    logger.info(f"Synced {synced_count} subscriptions from Stripe ({failed_count} failed)")
    return {
        'synced': synced_count,
        'failed': failed_count
    }


# ==================== OBSOLETE TASKS ====================
# The following tasks are no longer needed as Stripe handles these operations:
#
# - process_subscription_renewals() -> Stripe handles automatic renewals
# - retry_failed_payments() -> Stripe handles dunning and retries
# - send_renewal_reminders() -> Configure in Stripe dashboard
# - generate_invoices() -> Stripe generates invoices automatically
# - charge_customers() -> Stripe charges automatically on renewal
#
# All billing operations are now event-driven via Stripe webhooks.
