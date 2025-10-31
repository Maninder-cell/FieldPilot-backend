"""
Billing Views

Copyright (c) 2025 FieldPilot. All rights reserved.
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

logger = logging.getLogger(__name__)


def get_tenant(request):
    """Helper function to get tenant from request, handling both multi-tenant and single-tenant setups."""
    if hasattr(request, 'tenant'):
        return request.tenant
    # For development/testing without multi-tenancy
    from apps.tenants.models import Tenant
    tenant = Tenant.objects.first()
    if not tenant:
        raise ValueError("No tenant found. Please create a tenant first using the onboarding API.")
    return tenant


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
    description='Create a new subscription for the tenant (Admin only). Subscription management is handled by backend. Stripe payment is optional.',
    request=CreateSubscriptionSerializer,
    responses={
        201: SubscriptionSerializer,
        400: {'description': 'Invalid subscription data or tenant already has subscription'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
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
            
            # Calculate subscription periods
            now = timezone.now()
            if billing_cycle == 'yearly':
                period_end = now + timezone.timedelta(days=365)
            else:
                period_end = now + timezone.timedelta(days=30)
            
            # Create local subscription (backend manages this)
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                status='active',  # Start as active
                billing_cycle=billing_cycle,
                current_period_start=now,
                current_period_end=period_end,
                stripe_customer_id='',  # Optional - only if using Stripe
                stripe_subscription_id=''  # Optional - only if using Stripe
            )
            
            # If payment method provided, link to Stripe for future charging
            if payment_method_id:
                try:
                    from apps.billing.stripe_service import STRIPE_ENABLED
                    if STRIPE_ENABLED:
                        # Create or get Stripe customer
                        user = request.user
                        customer = StripeService.create_customer(tenant, user)
                        subscription.stripe_customer_id = customer.id
                        
                        # Attach payment method to customer
                        StripeService.attach_payment_method(
                            customer.id, payment_method_id, set_as_default=True
                        )
                        subscription.save()
                        logger.info(f"Stripe payment method linked to subscription {subscription.id}")
                    else:
                        logger.warning("Payment method provided but Stripe not enabled")
                except Exception as e:
                    logger.warning(f"Stripe setup failed, but subscription created: {str(e)}")
            
            # Update usage counts
            subscription.update_usage_counts()
            
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
    description='Update subscription plan or billing cycle (upgrade/downgrade) - Admin only',
    request=UpdateSubscriptionSerializer,
    responses={
        200: SubscriptionSerializer,
        400: {'description': 'Invalid update data'},
        404: {'description': 'No active subscription found'},
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
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
    description='Cancel current subscription immediately or at period end (Admin only)',
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
@permission_classes([IsAuthenticated, IsAdminUser])
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
@permission_classes([IsAuthenticated, IsAdminUser])
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
        customer_id = None
        
        # Check if tenant has a subscription with customer ID
        if hasattr(tenant, 'subscription') and tenant.subscription.stripe_customer_id:
            customer_id = tenant.subscription.stripe_customer_id
        else:
            # Create a new Stripe customer for the tenant
            user = request.user
            customer = StripeService.create_customer(tenant, user)
            customer_id = customer.id
            
            # If subscription exists, update it with customer ID
            if hasattr(tenant, 'subscription'):
                tenant.subscription.stripe_customer_id = customer_id
                tenant.subscription.save()
        
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
    description='Add payment method to customer account (Admin only)',
    request=PaymentMethodSerializer,
    responses={
        200: {'description': 'Payment method added successfully'},
        400: {'description': 'Invalid payment method data'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
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