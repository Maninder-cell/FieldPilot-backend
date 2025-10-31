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
import stripe
import json
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
        tenant = request.tenant
        
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
    description='Create a new subscription for the tenant (Admin only)',
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
            tenant = request.tenant
            plan = serializer.plan
            billing_cycle = serializer.validated_data['billing_cycle']
            payment_method_id = serializer.validated_data.get('payment_method_id')
            
            # Check if tenant already has a subscription
            if hasattr(tenant, 'subscription') and tenant.subscription.is_active:
                return error_response(
                    message="Tenant already has an active subscription",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Create Stripe subscription
            stripe_subscription = StripeService.create_subscription(
                tenant, plan, billing_cycle, payment_method_id
            )
            
            # Create local subscription
            subscription = Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                stripe_customer_id=stripe_subscription.customer,
                stripe_subscription_id=stripe_subscription.id,
                status=stripe_subscription.status,
                billing_cycle=billing_cycle,
                current_period_start=timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_start, tz=timezone.utc
                ),
                current_period_end=timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_end, tz=timezone.utc
                )
            )
            
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
            message="Failed to create subscription. Please try again.",
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
        tenant = request.tenant
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
        tenant = request.tenant
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
        tenant = request.tenant
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
        tenant = request.tenant
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
        tenant = request.tenant
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
        tenant = request.tenant
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
    summary='Create setup intent',
    description='Create Stripe setup intent for adding payment method (Admin only)',
    responses={
        200: {'type': 'object', 'properties': {'client_secret': {'type': 'string'}}},
        404: {'description': 'No subscription found'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_setup_intent(request):
    """
    Create setup intent for adding payment method.
    """
    try:
        tenant = request.tenant
        subscription = tenant.subscription
        
        setup_intent = StripeService.create_setup_intent(subscription.stripe_customer_id)
        
        return success_response(
            data={
                'client_secret': setup_intent.client_secret
            },
            message="Setup intent created successfully"
        )
        
    except Subscription.DoesNotExist:
        return error_response(
            message="No subscription found",
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Failed to create setup intent: {str(e)}")
        return error_response(
            message="Failed to create setup intent",
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
    try:
        if event['type'] == 'customer.subscription.updated':
            subscription_data = event['data']['object']
            StripeService.sync_subscription_from_stripe(subscription_data['id'])
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription_data = event['data']['object']
            try:
                subscription = Subscription.objects.get(
                    stripe_subscription_id=subscription_data['id']
                )
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
                subscription.save()
            except Subscription.DoesNotExist:
                pass
                
        elif event['type'] == 'invoice.payment_succeeded':
            invoice_data = event['data']['object']
            # Handle successful payment
            logger.info(f"Payment succeeded for invoice: {invoice_data['id']}")
            
        elif event['type'] == 'invoice.payment_failed':
            invoice_data = event['data']['object']
            # Handle failed payment
            logger.warning(f"Payment failed for invoice: {invoice_data['id']}")
            
        else:
            logger.info(f"Unhandled Stripe event type: {event['type']}")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=500)