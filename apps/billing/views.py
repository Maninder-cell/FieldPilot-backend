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

from .models import SubscriptionPlan, Subscription, Invoice, Payment
from .serializers import (
    SubscriptionPlanSerializer, SubscriptionSerializer, CreateSubscriptionSerializer,
    UpdateSubscriptionSerializer, InvoiceSerializer, PaymentSerializer,
    PaymentMethodSerializer, BillingOverviewSerializer
)
from .stripe_service import StripeService
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
    description='Get current tenant subscription details including usage and billing information',
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
    Get current tenant's subscription.
    """
    try:
        tenant = get_tenant(request)
        
        try:
            subscription = tenant.subscription
            # Update usage counts
            subscription.update_usage_counts()
            
            serializer = SubscriptionSerializer(subscription)
            
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
        logger.error(f"Failed to get current subscription: {str(e)}")
        return error_response(
            message="Failed to retrieve subscription",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Create subscription',
    description='Create a new subscription for the tenant (Owner/Admin only). Subscription management is handled by backend. Stripe payment is optional.',
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
    Subscription is managed by our backend. Stripe is only used for payment processing (optional).
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
            
            # Check if tenant has active trial
            now = timezone.now()
            is_in_trial = tenant.is_trial_active
            
            # Calculate subscription periods
            if is_in_trial:
                # Trial period: subscription starts now but billing starts after trial
                trial_start = now
                trial_end = tenant.trial_ends_at
                current_period_start = trial_end  # Billing starts after trial
                
                if billing_cycle == 'yearly':
                    current_period_end = trial_end + timezone.timedelta(days=365)
                else:
                    current_period_end = trial_end + timezone.timedelta(days=30)
                
                subscription_status = 'trialing'
                logger.info(f"Creating subscription in trial mode. Trial ends: {trial_end}")
            else:
                # No trial: subscription and billing start immediately
                trial_start = None
                trial_end = None
                current_period_start = now
                
                if billing_cycle == 'yearly':
                    current_period_end = now + timezone.timedelta(days=365)
                else:
                    current_period_end = now + timezone.timedelta(days=30)
                
                subscription_status = 'active'
                logger.info("Creating subscription without trial (trial already expired or not set)")
            
            # Create local subscription (backend manages this)
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                status=subscription_status,
                billing_cycle=billing_cycle,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                trial_start=trial_start,
                trial_end=trial_end,
                stripe_customer_id=None,  # Optional - only if using Stripe
                stripe_subscription_id=None  # Optional - only if using Stripe
            )
            
            # If payment method provided, save it but DON'T charge during trial
            if payment_method_id:
                try:
                    from apps.billing.stripe_service import STRIPE_ENABLED
                    if STRIPE_ENABLED:
                        import stripe
                        
                        # Get customer_id from the payment method (already attached by confirmCardSetup)
                        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
                        customer_id = payment_method.customer
                        
                        if not customer_id:
                            # Payment method not attached (shouldn't happen with confirmCardSetup)
                            user = request.user
                            customer = StripeService.create_customer(tenant, user)
                            customer_id = customer.id
                            logger.warning(f"Payment method not attached, created new customer: {customer_id}")
                        else:
                            logger.info(f"Using customer from payment method: {customer_id}")
                        
                        # Update subscription with customer ID
                        subscription.stripe_customer_id = customer_id
                        
                        # Set payment method as default (already attached via confirmCardSetup)
                        StripeService.attach_payment_method(
                            customer_id, payment_method_id, set_as_default=True
                        )
                        subscription.save()
                        logger.info(f"Stripe payment method saved for subscription {subscription.id}")
                        
                        # Only charge immediately if NOT in trial
                        if not is_in_trial:
                            # Calculate amount based on billing cycle
                            if billing_cycle == 'yearly':
                                amount = plan.price_yearly
                            else:
                                amount = plan.price_monthly
                            
                            # Charge customer immediately for first period
                            charge = StripeService.charge_customer(
                                customer_id,
                                amount,
                                f"Initial subscription - {plan.name} ({billing_cycle})",
                                payment_method_id=payment_method_id
                            )
                            
                            logger.info(f"Initial payment successful: {charge.id} - ${amount}")
                            
                            # Create invoice record
                            invoice = Invoice.objects.create(
                                tenant=tenant,
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
                            logger.info(f"Invoice created: {invoice.invoice_number}")
                            
                            # Create payment record
                            Payment.objects.create(
                                tenant=tenant,
                                invoice=invoice,
                                amount=amount,
                                status='succeeded',
                                payment_method='card',
                                stripe_charge_id=charge.id,
                                processed_at=timezone.now()
                            )
                            logger.info(f"Payment record created for charge: {charge.id}")
                        else:
                            logger.info(f"Trial active - payment will be charged after trial ends on {trial_end}")
                        
                    else:
                        logger.warning("Payment method provided but Stripe not enabled")
                except Exception as e:
                    # Rollback subscription if payment setup fails
                    subscription.delete()
                    logger.error(f"Payment setup failed: {str(e)}", exc_info=True)
                    return error_response(
                        message=f"Payment setup failed: {str(e)}",
                        status_code=status.HTTP_400_BAD_REQUEST
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
            
    except Exception as e:
        logger.error(f"Failed to create subscription: {str(e)}", exc_info=True)
        return error_response(
            message=f"Failed to create subscription: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Update subscription',
    description='Update subscription plan or billing cycle (upgrade/downgrade) - Owner/Admin only',
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
    Update current subscription (upgrade/downgrade).
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
            
            # Handle plan change
            if 'plan_slug' in validated_data:
                new_plan = serializer.plan
                new_billing_cycle = validated_data.get('billing_cycle', subscription.billing_cycle)
                
                # Update Stripe subscription
                StripeService.update_subscription(
                    subscription, new_plan, new_billing_cycle
                )
                
                # Update local subscription
                subscription.plan = new_plan
                subscription.billing_cycle = new_billing_cycle
            
            # Handle cancellation
            if 'cancel_at_period_end' in validated_data:
                cancel_at_period_end = validated_data['cancel_at_period_end']
                
                if cancel_at_period_end:
                    # Cancel at period end
                    StripeService.cancel_subscription(subscription, cancel_immediately=False)
                    subscription.cancel_at_period_end = True
                else:
                    # Reactivate subscription
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=False
                    )
                    subscription.cancel_at_period_end = False
            
            subscription.save()
            
            logger.info(f"Subscription updated for tenant {tenant.name}: {subscription.id}")
            
            return success_response(
                data=SubscriptionSerializer(subscription).data,
                message="Subscription updated successfully"
            )
            
    except Subscription.DoesNotExist:
        return error_response(
            message="No active subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to update subscription: {str(e)}", exc_info=True)
        return error_response(
            message="Failed to update subscription",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Cancel subscription',
    description='Cancel current subscription immediately or at period end (Owner/Admin only)',
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
    Cancel current subscription.
    """
    try:
        tenant = get_tenant(request)
        subscription = tenant.subscription
        
        cancel_immediately = request.data.get('cancel_immediately', False)
        cancellation_reason = request.data.get('reason', '')
        
        with transaction.atomic():
            # Cancel Stripe subscription
            StripeService.cancel_subscription(subscription, cancel_immediately)
            
            # Update local subscription
            if cancel_immediately:
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
            else:
                subscription.cancel_at_period_end = True
            
            subscription.cancellation_reason = cancellation_reason
            subscription.save()
            
            logger.info(f"Subscription canceled for tenant {tenant.name}: {subscription.id}")
            
            return success_response(
                data=SubscriptionSerializer(subscription).data,
                message="Subscription canceled successfully"
            )
            
    except Subscription.DoesNotExist:
        return error_response(
            message="No active subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {str(e)}")
        return error_response(
            message="Failed to cancel subscription",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get billing overview',
    description='Get billing dashboard with subscription, usage, and payment information',
    responses={
        200: BillingOverviewSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def billing_overview(request):
    """
    Get billing overview/dashboard.
    """
    try:
        tenant = get_tenant(request)
        serializer = BillingOverviewSerializer()
        
        return success_response(
            data=serializer.to_representation(tenant),
            message="Billing overview retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get billing overview: {str(e)}")
        return error_response(
            message="Failed to retrieve billing overview",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get invoices',
    description='Get list of tenant invoices with pagination',
    responses={
        200: InvoiceSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def invoices(request):
    """
    Get tenant's invoices.
    """
    try:
        tenant = get_tenant(request)
        invoices = tenant.invoices.all().order_by('-created_at')
        
        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(invoices, request)
        
        if page is not None:
            serializer = InvoiceSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Invoices retrieved successfully'
            })
        
        serializer = InvoiceSerializer(invoices, many=True)
        return success_response(
            data=serializer.data,
            message="Invoices retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get invoices: {str(e)}")
        return error_response(
            message="Failed to retrieve invoices",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Billing'],
    summary='Get payments',
    description='Get list of tenant payments with pagination',
    responses={
        200: PaymentSerializer(many=True),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@public_schema_only
def payments(request):
    """
    Get tenant's payments.
    """
    try:
        tenant = get_tenant(request)
        payments = tenant.payments.all().order_by('-created_at')
        
        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(payments, request)
        
        if page is not None:
            serializer = PaymentSerializer(page, many=True)
            return paginator.get_paginated_response({
                'success': True,
                'data': serializer.data,
                'message': 'Payments retrieved successfully'
            })
        
        serializer = PaymentSerializer(payments, many=True)
        return success_response(
            data=serializer.data,
            message="Payments retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to get payments: {str(e)}")
        return error_response(
            message="Failed to retrieve payments",
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
            # Create a new Stripe customer
            customer = StripeService.create_customer(tenant, user)
            customer_id = customer.id
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
    summary='Add payment method',
    description='Add payment method to customer account (Owner/Admin only)',
    request=PaymentMethodSerializer,
    responses={
        200: {'description': 'Payment method added successfully'},
        400: {'description': 'Invalid payment method data'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@public_schema_only
def add_payment_method(request):
    """
    Add payment method to customer.
    """
    serializer = PaymentMethodSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message="Invalid payment method data",
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        tenant = get_tenant(request)
        subscription = tenant.subscription
        
        payment_method_id = serializer.validated_data['payment_method_id']
        set_as_default = serializer.validated_data['set_as_default']
        
        # Attach payment method
        StripeService.attach_payment_method(
            subscription.stripe_customer_id,
            payment_method_id,
            set_as_default
        )
        
        return success_response(
            message="Payment method added successfully"
        )
        
    except Subscription.DoesNotExist:
        return error_response(
            message="No subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to add payment method: {str(e)}")
        return error_response(
            message="Failed to add payment method",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
    Handle Stripe webhooks.
    """
    try:
        import stripe
        from django.conf import settings
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("Invalid payload in Stripe webhook")
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in Stripe webhook")
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            logger.info(f"Payment succeeded: {payment_intent['id']}")
            
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            logger.warning(f"Payment failed: {payment_intent['id']}")
            
        else:
            logger.info(f"Unhandled Stripe event type: {event['type']}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=500)