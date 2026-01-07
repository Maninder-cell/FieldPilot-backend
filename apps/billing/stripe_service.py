"""
Stripe Integration Service

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.

Stripe is the single source of truth for all billing operations.
This service provides a comprehensive interface to Stripe's API.
"""
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from typing import Optional, List, Dict, Callable, Any
import logging
import time

logger = logging.getLogger(__name__)


class StripeError(Exception):
    """Base exception for Stripe-related errors with user-friendly messages."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class StripeCardError(StripeError):
    """Exception for card-related errors."""
    pass


class StripeConnectionError(StripeError):
    """Exception for connection-related errors."""
    pass


class StripeRateLimitError(StripeError):
    """Exception for rate limit errors."""
    pass

# Try to import Stripe, but make it optional
STRIPE_ENABLED = False
try:
    import stripe
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
    if stripe_key and stripe_key.strip() and not stripe_key.startswith('sk_test_dummy'):
        stripe.api_key = stripe_key
        STRIPE_ENABLED = True
        logger.info("Stripe billing system enabled")
    else:
        logger.warning("Stripe not configured - billing system disabled")
except ImportError:
    logger.warning("Stripe library not installed - billing system disabled")
except Exception as e:
    logger.error(f"Error configuring Stripe: {str(e)}")


def handle_stripe_errors(max_retries: int = 3):
    """
    Decorator to handle Stripe API errors with retry logic and user-friendly messages.
    
    Args:
        max_retries: Maximum number of retry attempts for transient failures
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                    
                except stripe.error.CardError as e:
                    # Card was declined - don't retry
                    logger.error(f"Card error in {func.__name__}: {e.user_message}", exc_info=True)
                    decline_code = e.code
                    user_message = e.user_message or "Your card was declined."
                    
                    # Provide more specific messages based on decline code
                    if decline_code == 'insufficient_funds':
                        user_message = "Your card has insufficient funds. Please use a different payment method."
                    elif decline_code == 'expired_card':
                        user_message = "Your card has expired. Please use a different payment method."
                    elif decline_code == 'incorrect_cvc':
                        user_message = "The card's security code (CVC) is incorrect. Please check and try again."
                    elif decline_code == 'card_declined':
                        user_message = "Your card was declined. Please contact your bank or use a different payment method."
                    
                    raise StripeCardError(user_message, e)
                
                except stripe.error.RateLimitError as e:
                    # Rate limit hit - retry with exponential backoff
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    logger.warning(f"Rate limit hit in {func.__name__}, attempt {attempt + 1}/{max_retries}. Waiting {wait_time}s")
                    
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        last_error = e
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} attempts", exc_info=True)
                        raise StripeRateLimitError(
                            "The billing service is currently experiencing high load. Please try again in a few moments.",
                            e
                        )
                
                except stripe.error.APIConnectionError as e:
                    # Network error - retry with exponential backoff
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    logger.warning(f"API connection error in {func.__name__}, attempt {attempt + 1}/{max_retries}. Waiting {wait_time}s")
                    
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        last_error = e
                        continue
                    else:
                        logger.error(f"API connection failed after {max_retries} attempts", exc_info=True)
                        raise StripeConnectionError(
                            "Unable to connect to the billing service. Please check your internet connection and try again.",
                            e
                        )
                
                except stripe.error.InvalidRequestError as e:
                    # Invalid parameters - don't retry
                    logger.error(f"Invalid request in {func.__name__}: {str(e)}", exc_info=True)
                    logger.error(f"Request details - Function: {func.__name__}, Args: {args}, Kwargs: {kwargs}")
                    raise StripeError(
                        "An error occurred while processing your request. Please contact support if this persists.",
                        e
                    )
                
                except stripe.error.AuthenticationError as e:
                    # Authentication error - don't retry
                    logger.critical(f"Stripe authentication error in {func.__name__}: {str(e)}", exc_info=True)
                    raise StripeError(
                        "Billing system configuration error. Please contact support.",
                        e
                    )
                
                except stripe.error.StripeError as e:
                    # Generic Stripe error - don't retry
                    logger.error(f"Stripe error in {func.__name__}: {str(e)}", exc_info=True)
                    raise StripeError(
                        "An error occurred with the billing service. Please try again or contact support.",
                        e
                    )
                
                except Exception as e:
                    # Unexpected error - don't retry
                    logger.error(f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True)
                    raise
            
            # Should never reach here, but just in case
            if last_error:
                raise last_error
        
        return wrapper
    return decorator


class StripeService:
    """
    Service class for comprehensive Stripe operations.
    Handles customers, subscriptions, invoices, payments, and payment methods.
    """
    
    # ==================== Customer Management ====================
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def get_or_create_customer(tenant, user) -> 'stripe.Customer':
        """
        Get existing Stripe customer or create a new one for the tenant.
        Searches Stripe by email to avoid creating duplicates.
        
        Args:
            tenant: Tenant model instance
            user: User model instance (for email and name)
            
        Returns:
            stripe.Customer object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled. Check your STRIPE_SECRET_KEY configuration.")
        
        # Check if tenant already has a subscription with customer ID
        if hasattr(tenant, 'subscription') and tenant.subscription and tenant.subscription.stripe_customer_id:
            customer_id = tenant.subscription.stripe_customer_id
            logger.info(f"Retrieving existing Stripe customer from subscription: {customer_id}")
            try:
                return stripe.Customer.retrieve(customer_id)
            except stripe.error.InvalidRequestError as e:
                if "No such customer" in str(e):
                    logger.warning(f"Customer {customer_id} not found in Stripe, will search or create new one")
                else:
                    raise
        
        # Search for existing customer by email to avoid duplicates
        logger.info(f"Searching for existing Stripe customer with email: {user.email}")
        existing_customers = stripe.Customer.list(email=user.email, limit=1)
        
        if existing_customers.data:
            customer = existing_customers.data[0]
            logger.info(f"Found existing Stripe customer: {customer.id} for email {user.email}")
            return customer
        
        # Create new customer
        logger.info(f"Creating new Stripe customer for tenant: {tenant.name}")
        
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
    
    # ==================== Subscription Management ====================
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def create_subscription(
        customer_id: str,
        price_id: str,
        payment_method_id: str,
        trial_end: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> tuple['stripe.Subscription', str]:
        """
        Create a Stripe subscription with trial handling.
        
        Args:
            customer_id: Stripe customer ID (may be overridden if payment method belongs to different customer)
            price_id: Stripe price ID for the subscription plan
            payment_method_id: Stripe payment method ID (already attached to customer)
            trial_end: Optional datetime for trial end (if in trial period)
            metadata: Optional metadata dict to attach to subscription
            
        Returns:
            Tuple of (stripe.Subscription object, actual customer_id used)
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Creating Stripe subscription for customer: {customer_id}")
        
        # Retrieve payment method to check which customer it belongs to
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        
        # If payment method is attached to a different customer, we need to use that customer instead
        if payment_method.customer and payment_method.customer != customer_id:
            logger.warning(f"Payment method {payment_method_id} is attached to customer {payment_method.customer}, but subscription requested for {customer_id}")
            logger.info(f"Using payment method's customer: {payment_method.customer}")
            customer_id = payment_method.customer
        elif not payment_method.customer:
            # Payment method not attached to any customer, attach it now
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            logger.info(f"Payment method attached to customer: {payment_method_id}")
        else:
            logger.info(f"Payment method already attached to correct customer: {payment_method_id}")
        
        # Set payment method as default
        stripe.Customer.modify(
            customer_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        logger.info(f"Payment method set as default: {payment_method_id}")
        
        # Build subscription parameters
        subscription_params = {
            'customer': customer_id,
            'items': [{'price': price_id}],
            'default_payment_method': payment_method_id,
            'metadata': metadata or {},
            'expand': ['latest_invoice.payment_intent']
        }
        
        # Add trial end if provided
        if trial_end:
            trial_end_timestamp = int(trial_end.timestamp())
            subscription_params['trial_end'] = trial_end_timestamp
            logger.info(f"Subscription will have trial until: {trial_end}")
        
        # Create Stripe subscription
        stripe_subscription = stripe.Subscription.create(**subscription_params)
        
        logger.info(f"Stripe subscription created: {stripe_subscription.id}")
        logger.info(f"Subscription status: {stripe_subscription.status}")
        
        return stripe_subscription, customer_id
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def get_subscription(subscription_id: str) -> 'stripe.Subscription':
        """
        Retrieve a subscription from Stripe.
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            stripe.Subscription object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Retrieving Stripe subscription: {subscription_id}")
        
        subscription = stripe.Subscription.retrieve(
            subscription_id,
            expand=['customer', 'default_payment_method', 'latest_invoice']
        )
        
        return subscription
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def update_subscription(
        subscription_id: str,
        price_id: Optional[str] = None,
        cancel_at_period_end: Optional[bool] = None
    ) -> 'stripe.Subscription':
        """
        Update a Stripe subscription (plan change or cancellation settings).
        
        Args:
            subscription_id: Stripe subscription ID
            price_id: Optional new price ID for plan upgrade/downgrade
            cancel_at_period_end: Optional boolean to cancel at period end
            
        Returns:
            stripe.Subscription object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Updating Stripe subscription: {subscription_id}")
        
        # Get current subscription
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        update_params = {}
        
        # Update price if provided (plan change)
        if price_id:
            update_params['items'] = [{
                'id': subscription['items']['data'][0]['id'],
                'price': price_id
            }]
            # Proration is automatic in Stripe
            logger.info(f"Changing subscription to price: {price_id}")
        
        # Update cancellation setting if provided
        if cancel_at_period_end is not None:
            update_params['cancel_at_period_end'] = cancel_at_period_end
            logger.info(f"Setting cancel_at_period_end to: {cancel_at_period_end}")
        
        # Apply updates
        if update_params:
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                **update_params
            )
            logger.info(f"Stripe subscription updated: {updated_subscription.id}")
            return updated_subscription
        
        return subscription
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def cancel_subscription(subscription_id: str, immediately: bool = False) -> 'stripe.Subscription':
        """
        Cancel a Stripe subscription.
        
        Args:
            subscription_id: Stripe subscription ID
            immediately: If True, cancel immediately. If False, cancel at period end.
            
        Returns:
            stripe.Subscription object (or deleted subscription object if immediate)
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Canceling Stripe subscription: {subscription_id} (immediate={immediately})")
        
        if immediately:
            # Cancel immediately (delete subscription)
            canceled_subscription = stripe.Subscription.delete(subscription_id)
            logger.info(f"Stripe subscription canceled immediately: {subscription_id}")
        else:
            # Cancel at period end
            canceled_subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"Stripe subscription set to cancel at period end: {subscription_id}")
        
        return canceled_subscription
    
    # ==================== Invoice Management ====================
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def list_invoices(
        customer_id: str,
        limit: int = 10,
        starting_after: Optional[str] = None
    ) -> List['stripe.Invoice']:
        """
        List invoices for a customer with pagination.
        
        Args:
            customer_id: Stripe customer ID
            limit: Number of invoices to return (default 10)
            starting_after: Cursor for pagination (invoice ID)
            
        Returns:
            List of stripe.Invoice objects
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Listing invoices for customer: {customer_id}")
        
        params = {
            'customer': customer_id,
            'limit': limit
        }
        
        if starting_after:
            params['starting_after'] = starting_after
        
        invoices = stripe.Invoice.list(**params)
        
        logger.info(f"Retrieved {len(invoices.data)} invoices for customer {customer_id}")
        return invoices.data
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def get_upcoming_invoice(subscription_id: str) -> Optional['stripe.Invoice']:
        """
        Get the upcoming invoice for a subscription.
        This shows what will be charged on the next billing cycle, including prorations.
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            stripe.Invoice object or None if no upcoming invoice
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        try:
            # Get the subscription to find the customer
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Use create_preview for flexible billing mode subscriptions (Stripe's new API)
            # This replaces the deprecated Invoice.upcoming() method
            upcoming_invoice = stripe.Invoice.create_preview(
                customer=subscription.customer,
                subscription=subscription_id,
                expand=['lines']  # Expand lines to get full details
            )
            
            return upcoming_invoice
        except stripe.error.InvalidRequestError as e:
            # No upcoming invoice (e.g., subscription canceled)
            logger.info(f"No upcoming invoice for subscription {subscription_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving upcoming invoice: {str(e)}")
            return None
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def get_invoice(invoice_id: str) -> 'stripe.Invoice':
        """
        Retrieve a single invoice from Stripe.
        
        Args:
            invoice_id: Stripe invoice ID
            
        Returns:
            stripe.Invoice object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Retrieving invoice: {invoice_id}")
        
        invoice = stripe.Invoice.retrieve(invoice_id)
        
        return invoice
    
    # ==================== Payment Management ====================
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def list_charges(
        customer_id: str,
        limit: int = 10,
        starting_after: Optional[str] = None
    ) -> List['stripe.Charge']:
        """
        List charges (payments) for a customer with pagination.
        
        Args:
            customer_id: Stripe customer ID
            limit: Number of charges to return (default 10)
            starting_after: Cursor for pagination (charge ID)
            
        Returns:
            List of stripe.Charge objects
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Listing charges for customer: {customer_id}")
        
        params = {
            'customer': customer_id,
            'limit': limit
        }
        
        if starting_after:
            params['starting_after'] = starting_after
        
        charges = stripe.Charge.list(**params)
        
        logger.info(f"Retrieved {len(charges.data)} charges for customer {customer_id}")
        return charges.data
    
    # ==================== Payment Method Management ====================
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def create_setup_intent(customer_id: str) -> 'stripe.SetupIntent':
        """
        Create a setup intent for saving payment method.
        Used to collect payment information for future charges.
        
        Args:
            customer_id: Stripe customer ID
            
        Returns:
            stripe.SetupIntent object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Creating setup intent for customer: {customer_id}")
        
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=['card'],
            usage='off_session'  # Allows charging without customer present
        )
        
        logger.info(f"Setup intent created: {setup_intent.id}")
        return setup_intent
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def list_payment_methods(customer_id: str) -> List['stripe.PaymentMethod']:
        """
        List payment methods for a customer.
        
        Args:
            customer_id: Stripe customer ID
            
        Returns:
            List of stripe.PaymentMethod objects
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Listing payment methods for customer: {customer_id}")
        
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card'
        )
        
        logger.info(f"Retrieved {len(payment_methods.data)} payment methods")
        return payment_methods.data
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def set_default_payment_method(customer_id: str, payment_method_id: str) -> 'stripe.Customer':
        """
        Set a payment method as the default for a customer.
        
        Args:
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID
            
        Returns:
            stripe.Customer object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Setting default payment method for customer {customer_id}: {payment_method_id}")
        
        customer = stripe.Customer.modify(
            customer_id,
            invoice_settings={'default_payment_method': payment_method_id}
        )
        
        logger.info(f"Default payment method updated for customer {customer_id}")
        return customer
    
    @staticmethod
    @handle_stripe_errors(max_retries=3)
    def detach_payment_method(payment_method_id: str) -> 'stripe.PaymentMethod':
        """
        Detach (remove) a payment method from a customer.
        
        Args:
            payment_method_id: Stripe payment method ID
            
        Returns:
            stripe.PaymentMethod object
        """
        if not STRIPE_ENABLED:
            raise ValueError("Stripe billing system is not enabled.")
        
        logger.info(f"Detaching payment method: {payment_method_id}")
        
        payment_method = stripe.PaymentMethod.detach(payment_method_id)
        
        logger.info(f"Payment method detached: {payment_method_id}")
        return payment_method
