"""
Stripe Integration Service

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.

NOTE: Stripe is ONLY used for payment processing.
Subscription management is handled by our backend.
"""
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import logging

from .models import Subscription, SubscriptionPlan, Invoice, Payment

logger = logging.getLogger(__name__)

# Try to import Stripe, but make it optional
STRIPE_ENABLED = False
try:
    import stripe
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if stripe_key and stripe_key.strip() and not stripe_key.startswith('sk_test_dummy'):
        stripe.api_key = stripe_key
        STRIPE_ENABLED = True
        logger.info("Stripe payment processing enabled")
    else:
        logger.warning("Stripe not configured - payment processing disabled")
except ImportError:
    logger.warning("Stripe library not installed - payment processing disabled")
except Exception as e:
    logger.error(f"Error configuring Stripe: {str(e)}")


class StripeService:
    """
    Service class for Stripe operations.
    """
    
    @staticmethod
    def create_customer(tenant, user):
        """
        Create a Stripe customer for the tenant.
        Only used for payment processing, not subscription management.
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe payment processing is not enabled. Check your STRIPE_SECRET_KEY configuration.")
        
        try:
            logger.info(f"Creating Stripe customer for tenant: {tenant.name}")
            
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}",
                metadata={
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'user_id': str(user.id)
                }
            )
            
            logger.info(f"Stripe customer created: {customer.id} for tenant {tenant.name}")
            return customer
            
        except Exception as e:
            logger.error(f"Failed to create Stripe customer: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def create_subscription(tenant, plan, billing_cycle, payment_method_id=None):
        """
        Create a Stripe subscription.
        """
        try:
            # Get or create Stripe customer
            subscription_obj = getattr(tenant, 'subscription', None)
            
            if subscription_obj and subscription_obj.stripe_customer_id:
                customer_id = subscription_obj.stripe_customer_id
            else:
                # Create new customer (need admin user)
                from apps.authentication.models import User
                from django_tenants.utils import schema_context
                
                with schema_context(tenant.schema_name):
                    admin_user = User.objects.filter(role='admin').first()
                    if not admin_user:
                        raise ValueError("No admin user found for tenant")
                
                customer = StripeService.create_customer(tenant, admin_user)
                customer_id = customer.id
            
            # Get price ID based on billing cycle
            price_id = (
                plan.stripe_price_id_yearly if billing_cycle == 'yearly' 
                else plan.stripe_price_id_monthly
            )
            
            if not price_id:
                raise ValueError(f"No Stripe price ID configured for plan {plan.name}")
            
            # Create subscription parameters
            subscription_params = {
                'customer': customer_id,
                'items': [{'price': price_id}],
                'metadata': {
                    'tenant_id': str(tenant.id),
                    'plan_id': str(plan.id),
                    'billing_cycle': billing_cycle
                },
                'expand': ['latest_invoice.payment_intent']
            }
            
            # Add payment method if provided
            if payment_method_id:
                subscription_params['default_payment_method'] = payment_method_id
            
            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(**subscription_params)
            
            logger.info(f"Stripe subscription created: {stripe_subscription.id}")
            return stripe_subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe subscription: {str(e)}")
            raise
    
    @staticmethod
    def update_subscription(subscription, new_plan=None, new_billing_cycle=None):
        """
        Update a Stripe subscription.
        """
        try:
            if not subscription.stripe_subscription_id:
                raise ValueError("No Stripe subscription ID found")
            
            # Get current Stripe subscription
            stripe_subscription = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            
            update_params = {}
            
            # Update plan if provided
            if new_plan:
                price_id = (
                    new_plan.stripe_price_id_yearly if new_billing_cycle == 'yearly'
                    else new_plan.stripe_price_id_monthly
                )
                
                if not price_id:
                    raise ValueError(f"No Stripe price ID for plan {new_plan.name}")
                
                update_params['items'] = [{
                    'id': stripe_subscription['items']['data'][0]['id'],
                    'price': price_id
                }]
                
                update_params['metadata'] = {
                    **stripe_subscription.metadata,
                    'plan_id': str(new_plan.id),
                    'billing_cycle': new_billing_cycle or subscription.billing_cycle
                }
            
            # Update subscription
            if update_params:
                updated_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    **update_params
                )
                
                logger.info(f"Stripe subscription updated: {updated_subscription.id}")
                return updated_subscription
            
            return stripe_subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update Stripe subscription: {str(e)}")
            raise
    
    @staticmethod
    def cancel_subscription(subscription, cancel_immediately=False):
        """
        Cancel a Stripe subscription.
        """
        try:
            if not subscription.stripe_subscription_id:
                raise ValueError("No Stripe subscription ID found")
            
            if cancel_immediately:
                # Cancel immediately
                canceled_subscription = stripe.Subscription.delete(
                    subscription.stripe_subscription_id
                )
            else:
                # Cancel at period end
                canceled_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            
            logger.info(f"Stripe subscription canceled: {canceled_subscription.id}")
            return canceled_subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel Stripe subscription: {str(e)}")
            raise
    
    @staticmethod
    def attach_payment_method(customer_id, payment_method_id, set_as_default=False):
        """
        Attach payment method to customer.
        """
        try:
            # Attach payment method
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default if requested
            if set_as_default:
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={'default_payment_method': payment_method_id}
                )
            
            logger.info(f"Payment method attached: {payment_method_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to attach payment method: {str(e)}")
            raise
    
    @staticmethod
    def get_customer_payment_methods(customer_id):
        """
        Get customer's payment methods.
        """
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return payment_methods.data
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to get payment methods: {str(e)}")
            raise
    
    @staticmethod
    def sync_subscription_from_stripe(stripe_subscription_id):
        """
        Sync subscription data from Stripe.
        """
        try:
            # Get Stripe subscription
            stripe_subscription = stripe.Subscription.retrieve(
                stripe_subscription_id,
                expand=['customer', 'items.data.price.product']
            )
            
            # Find local subscription
            try:
                subscription = Subscription.objects.get(
                    stripe_subscription_id=stripe_subscription_id
                )
            except Subscription.DoesNotExist:
                logger.warning(f"Local subscription not found for Stripe ID: {stripe_subscription_id}")
                return None
            
            # Update subscription data
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            )
            subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end
            
            if stripe_subscription.canceled_at:
                subscription.canceled_at = datetime.fromtimestamp(
                    stripe_subscription.canceled_at, tz=timezone.utc
                )
            
            subscription.save()
            
            logger.info(f"Subscription synced from Stripe: {subscription.id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to sync subscription from Stripe: {str(e)}")
            raise
    
    @staticmethod
    def create_setup_intent(customer_id):
        """
        Create a setup intent for saving payment method.
        This is ONLY for collecting payment information.
        The card will be saved for future recurring charges.
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe payment processing is not enabled. Check your STRIPE_SECRET_KEY configuration.")
        
        try:
            logger.info(f"Creating setup intent for customer: {customer_id}")
            
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=['card'],
                usage='off_session'  # Important: allows charging without customer present
            )
            
            logger.info(f"Setup intent created: {setup_intent.id}")
            return setup_intent
            
        except Exception as e:
            logger.error(f"Failed to create setup intent: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def charge_customer(customer_id, amount, description):
        """
        Charge a customer's saved payment method.
        Used for recurring subscription payments.
        
        Args:
            customer_id: Stripe customer ID
            amount: Amount to charge (Decimal)
            description: Charge description
            
        Returns:
            Stripe Charge object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe payment processing is not enabled.")
        
        try:
            logger.info(f"Charging customer {customer_id}: ${amount}")
            
            # Convert amount to cents (Stripe uses smallest currency unit)
            amount_cents = int(float(amount) * 100)
            
            # Create payment intent with saved payment method
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                customer=customer_id,
                description=description,
                off_session=True,  # Customer not present
                confirm=True,  # Automatically confirm and charge
                payment_method_types=['card']
            )
            
            logger.info(f"Payment successful: {payment_intent.id}")
            return payment_intent
            
        except stripe.error.CardError as e:
            # Card was declined
            logger.error(f"Card declined: {str(e)}")
            raise
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to charge customer: {str(e)}", exc_info=True)
            raise