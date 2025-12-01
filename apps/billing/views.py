"""
Billing Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiExample
import logging
import stripe
from .models import SubscriptionPlan, Subscription
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionSerializer, CreateSubscriptionSerializer,
    UpdateSubscriptionSerializer, StripeInvoiceSerializer, StripeChargeSerializer,
    PaymentMethodSerializer, StripePaymentMethodSerializer, BillingOverviewSerializer
)
from .stripe_service import (
    StripeService, StripeError, StripeCardError, 
    StripeConnectionError, StripeRateLimitError
)
from apps.core.responses import success_response, error_response
from apps.core.permissions import IsAdminUser
from functools import wraps

logger = logging.getLogger(__name__)


def public_schema_only(view_func):
    """
    Decorator to restrict view access to public schema only.
    Used for billing endpoints that should only be accessible from localhost.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.db import connection
        
        current_schema = connection.schema_name
        if current_schema != 'public':
            return error_response(
                message="This endpoint is only available from the onboarding portal. Please access via http://localhost:8000",
                status_code=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def get_tenant(request):
    """
    Helper function to get tenant from request user.
    Returns the tenant associated with the authenticated user.
    """
    # Get user's active tenant membership
    from django.db import connection
    
    # Switch to public schema to access tenant memberships
    connection.set_schema_to_public()
    
    membership = request.user.tenant_memberships.filter(is_active=True).first()
    
    if not membership:
        raise ValueError("No active tenant found for this user. Please create a company first using the onboarding API.")
    
    return membership.tenant


@extend_schema(
    tags=['Billing'],
    summary='Get subscription plans',
    description='Get all available subscription plans with pricing and features',
    responses={
        200: SubscriptionPlanSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
@public_schema_only
def subscription_plans(request):
    """
    Get all available subscription plans.
    """
    try:
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price_monthly')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        
        return success_response(
            data=serializer.data,
            message="Subscription plans retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get subscription plans: {str(e)}")
        return error_response(
            message="Failed to retrieve subscription plans",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get current subscription',
    description='Get current tenant subscription details from Stripe including usage and billing information',
    responses={
        200: SubscriptionSerializer,
        404: {'description': 'No active subscription found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def current_subscription(request):
    """
    Get current tenant's subscription from Stripe.
    Merges Stripe billing data with local usage tracking.
    """
    try:
        tenant = get_tenant(request)
        
        try:
            subscription = tenant.subscription
            
            # Update usage counts
            try:
                subscription.update_usage_counts()
            except Exception as e:
                logger.warning(f"Could not update usage counts: {str(e)}")
            
            # Fetch latest data from Stripe
            try:
                stripe_subscription = StripeService.get_subscription(subscription.stripe_subscription_id)
                
                # Update local status if changed
                if subscription.status != stripe_subscription.status:
                    subscription.status = stripe_subscription.status
                    subscription.save(update_fields=['status', 'updated_at'])
                    logger.info(f"Updated subscription status to: {stripe_subscription.status}")
                    
            except Exception as e:
                logger.error(f"Failed to fetch subscription from Stripe: {str(e)}")
                # Continue with local data if Stripe fetch fails
                stripe_subscription = None
            
            serializer = SubscriptionSerializer(subscription, context={'stripe_subscription': stripe_subscription})
            
            return success_response(
                data=serializer.data,
                message="Subscription retrieved successfully"
            )
            
        except Subscription.DoesNotExist:
            return success_response(
                data=None,
                message="No active subscription found"
            )
            
    except Exception as e:
        logger.error(f"Failed to get current subscription: {str(e)}", exc_info=True)
        return error_response(
            message="Failed to retrieve subscription",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Create subscription',
    description='Create a new subscription for the tenant (Owner/Admin only). Stripe manages all billing.',
    request=CreateSubscriptionSerializer,
    responses={
        201: SubscriptionSerializer,
        400: {'description': 'Invalid subscription data or tenant already has subscription'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def create_subscription(request):
    """
    Create a new subscription for the tenant.
    Stripe is the source of truth for all billing operations.
    """
    serializer = CreateSubscriptionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid subscription data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            tenant = get_tenant(request)
            plan = serializer.plan
            billing_cycle = serializer.validated_data['billing_cycle']
            payment_method_id = serializer.validated_data.get('payment_method_id')
            
            # Check if tenant already has a subscription
            if hasattr(tenant, 'subscription') and tenant.subscription.is_active:
                return error_response(
                    message="Tenant already has an active subscription",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Require payment method
            if not payment_method_id:
                return error_response(
                    message="Payment method is required",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create Stripe customer
            # First check if we have a pending customer from setup intent
            customer_id = request.session.get('pending_stripe_customer_id')
            if customer_id:
                logger.info(f"Reusing Stripe customer from setup intent: {customer_id}")
                # Clear the session variable after use
                del request.session['pending_stripe_customer_id']
            else:
                # Create new customer if not found in session
                user = request.user
                customer = StripeService.get_or_create_customer(tenant, user)
                customer_id = customer.id
                logger.info(f"Created new Stripe customer: {customer_id}")
            
            # Get price ID based on billing cycle
            price_id = (
                plan.stripe_price_id_yearly if billing_cycle == 'yearly' 
                else plan.stripe_price_id_monthly
            )
            
            if not price_id:
                return error_response(
                    message=f"No Stripe price ID configured for plan {plan.name}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Determine trial end
            # Check tenant's trial status (for new subscriptions)
            trial_end = None
            if tenant.trial_ends_at and timezone.now() < tenant.trial_ends_at:
                trial_end = tenant.trial_ends_at
                logger.info(f"Creating subscription with trial until: {trial_end}")
            else:
                logger.info("No active trial - subscription will start immediately")
            
            # Create Stripe subscription
            stripe_subscription, actual_customer_id = StripeService.create_subscription(
                customer_id=customer_id,
                price_id=price_id,
                payment_method_id=payment_method_id,
                trial_end=trial_end,
                metadata={
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'plan_id': str(plan.id),
                    'billing_cycle': billing_cycle
                }
            )
            
            # Create local subscription record using the actual customer ID
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                stripe_customer_id=actual_customer_id,
                stripe_subscription_id=stripe_subscription.id,
                status=stripe_subscription.status,
                billing_cycle=billing_cycle
            )
            
            # Update usage counts (ignore errors if tables don't exist yet)
            try:
                subscription.update_usage_counts()
            except Exception as e:
                logger.warning(f"Could not update usage counts: {str(e)}")
            
            logger.info(f"Subscription created for tenant {tenant.name}: {subscription.id}")
            
            return success_response(
                data=SubscriptionSerializer(subscription).data,
                message="Subscription created successfully",
                status_code=status.HTTP_201_CREATED
            )
            
    except StripeCardError as e:
        # Card was declined - return user-friendly message
        logger.error(f"Card error creating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED
        )
    except StripeConnectionError as e:
        # Network/connection error
        logger.error(f"Connection error creating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        # Rate limit exceeded
        logger.error(f"Rate limit error creating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        # Generic Stripe error
        logger.error(f"Stripe error creating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return error_response(
            message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to create subscription: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while creating your subscription. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Update subscription',
    description='Update subscription plan or billing cycle (upgrade/downgrade) via Stripe - Owner/Admin only',
    request=UpdateSubscriptionSerializer,
    responses={
        200: SubscriptionSerializer,
        400: {'description': 'Invalid update data'},
        404: {'description': 'No active subscription found'},
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@public_schema_only
def update_subscription(request):
    """
    Update current subscription (upgrade/downgrade) via Stripe.
    """
    try:
        tenant = get_tenant(request)
        subscription = tenant.subscription
        
        serializer = UpdateSubscriptionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message="Invalid update data",
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            validated_data = serializer.validated_data
            
            # Check if subscription is canceled - create new subscription instead
            if subscription.status == 'canceled':
                # Get plan and billing cycle
                new_plan = serializer.plan if 'plan_slug' in validated_data else subscription.plan
                new_billing_cycle = validated_data.get('billing_cycle', 'monthly')
                
                # Get price ID
                price_id = (
                    new_plan.stripe_price_id_yearly if new_billing_cycle == 'yearly'
                    else new_plan.stripe_price_id_monthly
                )
                
                if not price_id:
                    return error_response(
                        message=f"No Stripe price ID configured for plan {new_plan.name}",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Get customer's default payment method
                customer = stripe.Customer.retrieve(subscription.stripe_customer_id)
                payment_method_id = customer.invoice_settings.default_payment_method
                
                if not payment_method_id:
                    return error_response(
                        message="No payment method found. Please add a payment method first.",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                # Create new Stripe subscription using existing customer ID
                stripe_subscription, actual_customer_id = StripeService.create_subscription(
                    customer_id=subscription.stripe_customer_id,
                    price_id=price_id,
                    payment_method_id=payment_method_id,
                    trial_end=None  # No trial for resubscription
                )
                
                # Update existing subscription record
                subscription.plan = new_plan
                subscription.stripe_subscription_id = stripe_subscription.id
                subscription.status = stripe_subscription.status
                subscription.current_period_start = timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_start, tz=timezone.utc
                )
                subscription.current_period_end = timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_end, tz=timezone.utc
                )
                subscription.cancellation_reason = ''
                subscription.save()
                
                logger.info(f"Resubscribed tenant {tenant.name} to plan {new_plan.name}")
                
                return success_response(
                    data=SubscriptionSerializer(subscription, context={'stripe_subscription': stripe_subscription}).data,
                    message="Subscription reactivated successfully"
                )
            
            # Handle plan change for active subscriptions
            if 'plan_slug' in validated_data:
                new_plan = serializer.plan
                new_billing_cycle = validated_data.get('billing_cycle', 'monthly')
                
                # Get new price ID
                price_id = (
                    new_plan.stripe_price_id_yearly if new_billing_cycle == 'yearly'
                    else new_plan.stripe_price_id_monthly
                )
                
                if not price_id:
                    return error_response(
                        message=f"No Stripe price ID configured for plan {new_plan.name}",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                # Update Stripe subscription (proration is automatic)
                stripe_subscription = StripeService.update_subscription(
                    subscription.stripe_subscription_id,
                    price_id=price_id
                )
                
                # Update local subscription
                subscription.plan = new_plan
                subscription.status = stripe_subscription.status
                subscription.save()
                
                logger.info(f"Subscription plan updated for tenant {tenant.name}: {new_plan.name}")
            
            # Handle cancellation setting
            if 'cancel_at_period_end' in validated_data:
                cancel_at_period_end = validated_data['cancel_at_period_end']
                
                # Update Stripe subscription
                stripe_subscription = StripeService.update_subscription(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=cancel_at_period_end
                )
                
                # Update local status
                subscription.status = stripe_subscription.status
                subscription.save()
                
                action = "set to cancel at period end" if cancel_at_period_end else "reactivated"
                logger.info(f"Subscription {action} for tenant {tenant.name}")
            
            # Fetch updated subscription from Stripe
            stripe_subscription = StripeService.get_subscription(subscription.stripe_subscription_id)
            
            return success_response(
                data=SubscriptionSerializer(subscription, context={'stripe_subscription': stripe_subscription}).data,
                message="Subscription updated successfully"
            )
            
    except Subscription.DoesNotExist:
        return error_response(
            message="No active subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except StripeCardError as e:
        logger.error(f"Card error updating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED
        )
    except StripeConnectionError as e:
        logger.error(f"Connection error updating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        logger.error(f"Rate limit error updating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        logger.error(f"Stripe error updating subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to update subscription: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while updating your subscription. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Cancel subscription',
    description='Cancel current subscription via Stripe immediately or at period end (Owner/Admin only)',
    request={'type': 'object', 'properties': {
        'cancel_immediately': {'type': 'boolean', 'default': False},
        'reason': {'type': 'string'}
    }},
    responses={
        200: SubscriptionSerializer,
        404: {'description': 'No active subscription found'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def cancel_subscription(request):
    """
    Cancel current subscription via Stripe.
    """
    try:
        tenant = get_tenant(request)
        subscription = tenant.subscription
        
        cancel_immediately = request.data.get('cancel_immediately', False)
        cancellation_reason = request.data.get('reason', '')
        
        with transaction.atomic():
            # Cancel Stripe subscription
            stripe_subscription = StripeService.cancel_subscription(
                subscription.stripe_subscription_id,
                immediately=cancel_immediately
            )
            
            # Update local subscription
            subscription.status = stripe_subscription.status
            subscription.cancellation_reason = cancellation_reason
            subscription.save()
            
            action = "immediately" if cancel_immediately else "at period end"
            logger.info(f"Subscription canceled {action} for tenant {tenant.name}: {subscription.id}")
            
            return success_response(
                data=SubscriptionSerializer(subscription, context={'stripe_subscription': stripe_subscription}).data,
                message="Subscription canceled successfully"
            )
            
    except Subscription.DoesNotExist:
        return error_response(
            message="No active subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except StripeConnectionError as e:
        logger.error(f"Connection error canceling subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        logger.error(f"Rate limit error canceling subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        logger.error(f"Stripe error canceling subscription: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while canceling your subscription. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get billing overview',
    description='Get billing dashboard with subscription, usage, and payment information from Stripe',
    responses={
        200: BillingOverviewSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def billing_overview(request):
    """
    Get billing overview/dashboard from Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return success_response(
                data={
                    'subscription': None,
                    'current_invoice': None,
                    'recent_payments': [],
                    'usage_summary': {}
                },
                message="No subscription found"
            )
        
        subscription = tenant.subscription
        customer_id = subscription.stripe_customer_id
        
        # Fetch subscription from Stripe
        try:
            stripe_subscription = StripeService.get_subscription(subscription.stripe_subscription_id)
        except Exception as e:
            logger.error(f"Failed to fetch subscription from Stripe: {str(e)}")
            stripe_subscription = None
        
        # Fetch latest invoice from Stripe
        try:
            stripe_invoices = StripeService.list_invoices(customer_id=customer_id, limit=1)
            current_invoice = stripe_invoices[0] if stripe_invoices else None
        except Exception as e:
            logger.error(f"Failed to fetch invoices from Stripe: {str(e)}")
            current_invoice = None
        
        # Fetch recent payments from Stripe
        try:
            recent_charges = StripeService.list_charges(customer_id=customer_id, limit=5)
        except Exception as e:
            logger.error(f"Failed to fetch charges from Stripe: {str(e)}")
            recent_charges = []
        
        # Update usage counts
        try:
            subscription.update_usage_counts()
        except Exception as e:
            logger.warning(f"Could not update usage counts: {str(e)}")
        
        # Build response
        serializer = BillingOverviewSerializer(context={
            'subscription': subscription,
            'stripe_subscription': stripe_subscription,
            'current_invoice': current_invoice,
            'recent_charges': recent_charges
        })
        
        return success_response(
            data=serializer.to_representation(tenant),
            message="Billing overview retrieved successfully"
        )
    
    except StripeConnectionError as e:
        logger.error(f"Connection error getting billing overview: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        logger.error(f"Rate limit error getting billing overview: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        logger.error(f"Stripe error getting billing overview: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to get billing overview: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while retrieving billing information. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get invoices',
    description='Get list of tenant invoices from Stripe with pagination',
    responses={
        200: StripeInvoiceSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def invoices(request):
    """
    Get tenant's invoices from Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return success_response(
                data=[],
                message="No subscription found"
            )
        
        subscription = tenant.subscription
        customer_id = subscription.stripe_customer_id
        
        # Get pagination parameters
        limit = int(request.GET.get('limit', 10))
        starting_after = request.GET.get('starting_after', None)
        
        # Fetch invoices from Stripe
        stripe_invoices = StripeService.list_invoices(
            customer_id=customer_id,
            limit=limit,
            starting_after=starting_after
        )
        
        # Serialize invoices
        serializer = StripeInvoiceSerializer(stripe_invoices, many=True)
        
        return success_response(
            data=serializer.data,
            message="Invoices retrieved successfully"
        )
    
    except StripeConnectionError as e:
        logger.error(f"Connection error getting invoices: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        logger.error(f"Rate limit error getting invoices: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        logger.error(f"Stripe error getting invoices: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to get invoices: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while retrieving invoices. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get payments',
    description='Get list of tenant payments from Stripe with pagination',
    responses={
        200: StripeChargeSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def payments(request):
    """
    Get tenant's payments (charges) from Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return success_response(
                data=[],
                message="No subscription found"
            )
        
        subscription = tenant.subscription
        customer_id = subscription.stripe_customer_id
        
        # Get pagination parameters
        limit = int(request.GET.get('limit', 10))
        starting_after = request.GET.get('starting_after', None)
        
        # Fetch charges from Stripe
        stripe_charges = StripeService.list_charges(
            customer_id=customer_id,
            limit=limit,
            starting_after=starting_after
        )
        
        # Serialize charges
        serializer = StripeChargeSerializer(stripe_charges, many=True)
        
        return success_response(
            data=serializer.data,
            message="Payments retrieved successfully"
        )
    
    except StripeConnectionError as e:
        logger.error(f"Connection error getting payments: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except StripeRateLimitError as e:
        logger.error(f"Rate limit error getting payments: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StripeError as e:
        logger.error(f"Stripe error getting payments: {e.message}")
        return error_response(
            message=e.message,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to get payments: {str(e)}", exc_info=True)
        return error_response(
            message="An unexpected error occurred while retrieving payments. Please try again or contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Create setup intent',
    description='Create Stripe setup intent for saving payment method. This saves the card for future recurring charges.',
    responses={
        200: {'type': 'object', 'properties': {
            'client_secret': {'type': 'string'},
            'customer_id': {'type': 'string'}
        }},
        400: {'description': 'Stripe not configured'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def create_setup_intent(request):
    """
    Create setup intent for saving payment method.
    This saves the card for future recurring charges (monthly/yearly).
    """
    try:
        from apps.billing.stripe_service import STRIPE_ENABLED
        
        if not STRIPE_ENABLED:
            return error_response(
                message="Stripe payment processing is not enabled. Please configure STRIPE_SECRET_KEY in your .env file.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        tenant = get_tenant(request)
        user = request.user
        customer_id = None
        
        # Check if tenant already has a Stripe customer
        if hasattr(tenant, 'subscription') and tenant.subscription and tenant.subscription.stripe_customer_id:
            # Reuse existing customer
            customer_id = tenant.subscription.stripe_customer_id
            logger.info(f"Reusing existing Stripe customer: {customer_id}")
        else:
            # Create a new Stripe customer and store it in session for reuse
            customer = StripeService.get_or_create_customer(tenant, user)
            customer_id = customer.id
            # Store customer_id in session so create_subscription can reuse it
            request.session['pending_stripe_customer_id'] = customer_id
            logger.info(f"Created new Stripe customer: {customer_id}")
        
        setup_intent = StripeService.create_setup_intent(customer_id)
        
        return success_response(
            data={
                'client_secret': setup_intent.client_secret,
                'customer_id': customer_id
            },
            message="Setup intent created successfully"
        )
        
    except ValueError as e:
        return error_response(
            message=str(e),
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Failed to create setup intent: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to create setup intent: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='List payment methods',
    description='Get list of payment methods for the customer (Owner/Admin only)',
    responses={
        200: StripePaymentMethodSerializer(many=True),
        404: {'description': 'No subscription found'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def list_payment_methods(request):
    """
    List payment methods from Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return error_response(
                message="No subscription found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        subscription = tenant.subscription
        customer_id = subscription.stripe_customer_id
        
        # Fetch customer to get default payment method
        customer = stripe.Customer.retrieve(customer_id)
        default_payment_method_id = customer.invoice_settings.default_payment_method if customer.invoice_settings else None
        
        # Fetch payment methods from Stripe
        payment_methods = StripeService.list_payment_methods(customer_id)
        
        # Serialize payment methods with default flag
        from .serializers import StripePaymentMethodSerializer
        serializer = StripePaymentMethodSerializer(
            payment_methods, 
            many=True,
            context={'default_payment_method_id': default_payment_method_id}
        )
        
        return success_response(
            data=serializer.data,
            message="Payment methods retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to list payment methods: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to retrieve payment methods: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Set default payment method',
    description='Set a payment method as default for the customer (Owner/Admin only)',
    request={'type': 'object', 'properties': {
        'payment_method_id': {'type': 'string'}
    }},
    responses={
        200: {'description': 'Default payment method updated successfully'},
        400: {'description': 'Invalid request data'},
        404: {'description': 'No subscription found'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def set_default_payment_method(request):
    """
    Set default payment method in Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return error_response(
                message="No subscription found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        subscription = tenant.subscription
        customer_id = subscription.stripe_customer_id
        
        payment_method_id = request.data.get('payment_method_id')
        if not payment_method_id:
            return error_response(
                message="payment_method_id is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Set default payment method in Stripe
        StripeService.set_default_payment_method(customer_id, payment_method_id)
        
        return success_response(
            message="Default payment method updated successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to set default payment method: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to set default payment method: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Remove payment method',
    description='Remove a payment method from the customer (Owner/Admin only)',
    responses={
        200: {'description': 'Payment method removed successfully'},
        404: {'description': 'No subscription found'},
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@public_schema_only
def remove_payment_method(request, payment_method_id):
    """
    Remove (detach) payment method from Stripe.
    """
    try:
        tenant = get_tenant(request)
        
        # Check if tenant has a subscription
        if not hasattr(tenant, 'subscription') or not tenant.subscription:
            return error_response(
                message="No subscription found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Detach payment method from Stripe
        StripeService.detach_payment_method(payment_method_id)
        
        return success_response(
            message="Payment method removed successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to remove payment method: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to remove payment method: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==================== Webhook Event Handlers ====================

def handle_subscription_updated(event_data):
    """Handle customer.subscription.updated event."""
    try:
        stripe_subscription = event_data['object']
        subscription_id = stripe_subscription['id']
        
        # Find local subscription
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
            
            # Update status
            old_status = subscription.status
            subscription.status = stripe_subscription['status']
            subscription.save(update_fields=['status', 'updated_at'])
            
            logger.info(f"Subscription {subscription_id} status updated: {old_status} -> {subscription.status}")
            
        except Subscription.DoesNotExist:
            logger.warning(f"Local subscription not found for Stripe ID: {subscription_id}")
            
    except Exception as e:
        logger.error(f"Error handling subscription.updated: {str(e)}", exc_info=True)


def handle_subscription_deleted(event_data):
    """Handle customer.subscription.deleted event."""
    try:
        stripe_subscription = event_data['object']
        subscription_id = stripe_subscription['id']
        
        # Find local subscription
        try:
            subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
            
            # Mark as canceled
            subscription.status = 'canceled'
            subscription.save(update_fields=['status', 'updated_at'])
            
            logger.info(f"Subscription {subscription_id} marked as canceled")
            
        except Subscription.DoesNotExist:
            logger.warning(f"Local subscription not found for Stripe ID: {subscription_id}")
            
    except Exception as e:
        logger.error(f"Error handling subscription.deleted: {str(e)}", exc_info=True)


def handle_invoice_payment_succeeded(event_data):
    """Handle invoice.payment_succeeded event."""
    try:
        invoice = event_data['object']
        invoice_id = invoice['id']
        amount_paid = invoice['amount_paid'] / 100  # Convert from cents
        
        logger.info(f"Invoice payment succeeded: {invoice_id} - ${amount_paid}")
        
        # Optionally update subscription status if needed
        if invoice.get('subscription'):
            subscription_id = invoice['subscription']
            try:
                subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
                if subscription.status != 'active':
                    subscription.status = 'active'
                    subscription.save(update_fields=['status', 'updated_at'])
                    logger.info(f"Subscription {subscription_id} status updated to active after payment")
            except Subscription.DoesNotExist:
                pass
                
    except Exception as e:
        logger.error(f"Error handling invoice.payment_succeeded: {str(e)}", exc_info=True)


def handle_invoice_payment_failed(event_data):
    """Handle invoice.payment_failed event."""
    try:
        invoice = event_data['object']
        invoice_id = invoice['id']
        customer_id = invoice['customer']
        
        logger.warning(f"Invoice payment failed: {invoice_id} for customer {customer_id}")
        
        # Update subscription status to past_due
        if invoice.get('subscription'):
            subscription_id = invoice['subscription']
            try:
                subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
                subscription.status = 'past_due'
                subscription.save(update_fields=['status', 'updated_at'])
                logger.info(f"Subscription {subscription_id} status updated to past_due")
            except Subscription.DoesNotExist:
                logger.warning(f"Local subscription not found for Stripe ID: {subscription_id}")
                
    except Exception as e:
        logger.error(f"Error handling invoice.payment_failed: {str(e)}", exc_info=True)


@extend_schema(
    tags=['Billing'],
    summary='Stripe webhook',
    description='Handle Stripe webhook events (for Stripe use only)',
    exclude=True  # Hide from public API docs
)
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    Handle Stripe webhooks with comprehensive event handlers.
    """
    try:
        from django.conf import settings
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        # Verify webhook signature
        try:
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
            if not webhook_secret:
                logger.error("STRIPE_WEBHOOK_SECRET not configured")
                return HttpResponse(status=500)
            
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid payload in Stripe webhook: {str(e)}")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature in Stripe webhook: {str(e)}")
            return HttpResponse(status=400)
        
        # Get event type and data
        event_type = event['type']
        event_data = event['data']
        
        logger.info(f"Received Stripe webhook: {event_type}")
        
        # Route to appropriate handler
        handlers = {
            'customer.subscription.updated': handle_subscription_updated,
            'customer.subscription.deleted': handle_subscription_deleted,
            'invoice.payment_succeeded': handle_invoice_payment_succeeded,
            'invoice.payment_failed': handle_invoice_payment_failed,
        }
        
        handler = handlers.get(event_type)
        if handler:
            handler(event_data)
        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")
        
        # Always return 200 to acknowledge receipt
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}", exc_info=True)
        # Return 500 so Stripe will retry
        return HttpResponse(status=500)