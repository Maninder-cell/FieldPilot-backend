"""
Billing Celery Tasks

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import logging

from .models import Subscription, Invoice, Payment
from .stripe_service import StripeService, STRIPE_ENABLED

logger = logging.getLogger(__name__)


@shared_task
def process_subscription_renewals():
    """
    Process subscription renewals for subscriptions ending today.
    Also handles trial-to-active conversion and first payment after trial.
    This should run daily via Celery beat.
    """
    logger.info("Starting subscription renewal processing...")
    
    today = timezone.now().date()
    
    # Find subscriptions that end today and are active
    subscriptions_to_renew = Subscription.objects.filter(
        current_period_end__date=today,
        status='active',
        cancel_at_period_end=False
    )
    
    # Find subscriptions where trial ends today
    subscriptions_trial_ending = Subscription.objects.filter(
        trial_end__date=today,
        status='trialing'
    )
    
    renewed_count = 0
    failed_count = 0
    trial_converted_count = 0
    
    # Process trial-to-active conversions first
    for subscription in subscriptions_trial_ending:
        try:
            logger.info(f"Processing trial end for subscription {subscription.id}")
            
            # Calculate amount
            if subscription.billing_cycle == 'yearly':
                amount = subscription.plan.price_yearly
            else:
                amount = subscription.plan.price_monthly
            
            # Try to charge via Stripe if enabled and customer has payment method
            payment_successful = False
            stripe_charge_id = None
            
            if STRIPE_ENABLED and subscription.stripe_customer_id:
                try:
                    charge = StripeService.charge_customer(
                        subscription.stripe_customer_id,
                        amount,
                        f"First payment after trial - {subscription.plan.name}"
                    )
                    payment_successful = True
                    stripe_charge_id = charge.id
                    logger.info(f"Trial conversion payment successful: {charge.id} - ${amount}")
                except Exception as e:
                    logger.error(f"Trial conversion payment failed for subscription {subscription.id}: {str(e)}")
                    # Mark subscription as past_due
                    subscription.status = 'past_due'
                    subscription.save()
                    failed_count += 1
                    continue
            else:
                # No Stripe - assume payment handled externally
                payment_successful = True
                logger.info(f"Stripe not enabled, marking trial as converted without payment")
            
            if payment_successful:
                # Create invoice
                invoice = Invoice.objects.create(
                    tenant=subscription.tenant,
                    subscription=subscription,
                    subtotal=amount,
                    total=amount,
                    status='paid',
                    period_start=subscription.current_period_start,
                    period_end=subscription.current_period_end,
                    due_date=subscription.current_period_end,
                    paid_at=timezone.now()
                )
                invoice.generate_invoice_number()
                
                # Create payment record
                Payment.objects.create(
                    tenant=subscription.tenant,
                    invoice=invoice,
                    amount=amount,
                    status='succeeded',
                    payment_method='card',
                    stripe_charge_id=stripe_charge_id or '',
                    processed_at=timezone.now()
                )
                
                # Convert trial to active
                subscription.status = 'active'
                subscription.save()
                
                trial_converted_count += 1
                logger.info(f"Trial converted to active for subscription {subscription.id}")
                
        except Exception as e:
            logger.error(f"Failed to process trial end for subscription {subscription.id}: {str(e)}")
            failed_count += 1
    
    # Process regular renewals
    for subscription in subscriptions_to_renew:
        try:
            logger.info(f"Processing renewal for subscription {subscription.id}")
            
            # Calculate new period
            if subscription.billing_cycle == 'yearly':
                new_period_end = subscription.current_period_end + timedelta(days=365)
            else:
                new_period_end = subscription.current_period_end + timedelta(days=30)
            
            # Calculate amount
            if subscription.billing_cycle == 'yearly':
                amount = subscription.plan.price_yearly
            else:
                amount = subscription.plan.price_monthly
            
            # Try to charge via Stripe if enabled and customer has payment method
            payment_successful = False
            stripe_charge_id = None
            
            if STRIPE_ENABLED and subscription.stripe_customer_id:
                try:
                    charge = StripeService.charge_customer(
                        subscription.stripe_customer_id,
                        amount,
                        f"Subscription renewal - {subscription.plan.name}"
                    )
                    payment_successful = True
                    stripe_charge_id = charge.id
                    logger.info(f"Payment successful: {charge.id}")
                except Exception as e:
                    logger.error(f"Payment failed for subscription {subscription.id}: {str(e)}")
                    # Mark subscription as past_due
                    subscription.status = 'past_due'
                    subscription.save()
                    failed_count += 1
                    continue
            else:
                # No Stripe - assume payment handled externally
                payment_successful = True
                logger.info(f"Stripe not enabled, marking as renewed without payment")
            
            if payment_successful:
                # Create invoice
                invoice = Invoice.objects.create(
                    tenant=subscription.tenant,
                    subscription=subscription,
                    subtotal=amount,
                    total=amount,
                    status='paid',
                    period_start=subscription.current_period_end,
                    period_end=new_period_end,
                    due_date=new_period_end,
                    paid_at=timezone.now()
                )
                invoice.generate_invoice_number()
                
                # Create payment record
                Payment.objects.create(
                    tenant=subscription.tenant,
                    invoice=invoice,
                    amount=amount,
                    status='succeeded',
                    payment_method='card',
                    stripe_charge_id=stripe_charge_id or '',
                    processed_at=timezone.now()
                )
                
                # Update subscription period
                subscription.current_period_start = subscription.current_period_end
                subscription.current_period_end = new_period_end
                subscription.save()
                
                renewed_count += 1
                logger.info(f"Subscription {subscription.id} renewed successfully")
                
        except Exception as e:
            logger.error(f"Failed to process renewal for subscription {subscription.id}: {str(e)}", exc_info=True)
            failed_count += 1
    
    logger.info(f"Renewal processing complete. Trial conversions: {trial_converted_count}, Renewed: {renewed_count}, Failed: {failed_count}")
    return {
        'trial_converted': trial_converted_count,
        'renewed': renewed_count,
        'failed': failed_count
    }


@shared_task
def retry_failed_payments():
    """
    Retry failed payments for past_due subscriptions.
    Runs daily to attempt charging past_due subscriptions.
    """
    logger.info("Starting failed payment retry...")
    
    past_due_subscriptions = Subscription.objects.filter(
        status='past_due'
    )
    
    success_count = 0
    failed_count = 0
    
    for subscription in past_due_subscriptions:
        try:
            if not STRIPE_ENABLED or not subscription.stripe_customer_id:
                continue
            
            # Calculate amount
            if subscription.billing_cycle == 'yearly':
                amount = subscription.plan.price_yearly
            else:
                amount = subscription.plan.price_monthly
            
            # Try to charge
            charge = StripeService.charge_customer(
                subscription.stripe_customer_id,
                amount,
                f"Retry payment - {subscription.plan.name}"
            )
            
            # Payment successful - reactivate subscription
            subscription.status = 'active'
            subscription.save()
            
            # Create payment record
            Payment.objects.create(
                tenant=subscription.tenant,
                amount=amount,
                status='succeeded',
                payment_method='card',
                stripe_charge_id=charge.id,
                processed_at=timezone.now()
            )
            
            success_count += 1
            logger.info(f"Payment retry successful for subscription {subscription.id}")
            
        except Exception as e:
            logger.error(f"Payment retry failed for subscription {subscription.id}: {str(e)}")
            failed_count += 1
            
            # After 3 failed attempts, cancel subscription
            failed_payments = Payment.objects.filter(
                tenant=subscription.tenant,
                status='failed'
            ).count()
            
            if failed_payments >= 3:
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
                subscription.cancellation_reason = 'Payment failed after 3 attempts'
                subscription.save()
                logger.warning(f"Subscription {subscription.id} canceled due to failed payments")
    
    logger.info(f"Payment retry complete. Success: {success_count}, Failed: {failed_count}")
    return {
        'success': success_count,
        'failed': failed_count
    }


@shared_task
def send_renewal_reminders():
    """
    Send email reminders for subscriptions expiring soon.
    Runs daily to notify users 7 days before renewal.
    """
    logger.info("Sending renewal reminders...")
    
    seven_days_from_now = timezone.now() + timedelta(days=7)
    
    subscriptions_expiring_soon = Subscription.objects.filter(
        current_period_end__date=seven_days_from_now.date(),
        status='active'
    )
    
    sent_count = 0
    
    for subscription in subscriptions_expiring_soon:
        try:
            # TODO: Send email notification
            # send_mail(
            #     subject=f'Your {subscription.plan.name} subscription renews in 7 days',
            #     message=f'Your subscription will renew on {subscription.current_period_end}',
            #     from_email=settings.DEFAULT_FROM_EMAIL,
            #     recipient_list=[subscription.tenant.company_email]
            # )
            
            logger.info(f"Renewal reminder sent for subscription {subscription.id}")
            sent_count += 1
            
        except Exception as e:
            logger.error(f"Failed to send reminder for subscription {subscription.id}: {str(e)}")
    
    logger.info(f"Sent {sent_count} renewal reminders")
    return {'sent': sent_count}


@shared_task
def update_all_usage_counts():
    """
    Update usage counts for all active subscriptions.
    Runs daily to track resource usage.
    """
    logger.info("Updating usage counts for all subscriptions...")
    
    active_subscriptions = Subscription.objects.filter(
        status__in=['active', 'trialing']
    )
    
    updated_count = 0
    
    for subscription in active_subscriptions:
        try:
            subscription.update_usage_counts()
            updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update usage for subscription {subscription.id}: {str(e)}")
    
    logger.info(f"Updated usage counts for {updated_count} subscriptions")
    return {'updated': updated_count}
