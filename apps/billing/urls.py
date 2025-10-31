"""
Billing URLs

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Subscription plans
    path('plans/', views.subscription_plans, name='subscription_plans'),
    
    # Subscription management
    path('subscription/', views.current_subscription, name='current_subscription'),
    path('subscription/create/', views.create_subscription, name='create_subscription'),
    path('subscription/update/', views.update_subscription, name='update_subscription'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Billing overview
    path('overview/', views.billing_overview, name='billing_overview'),
    
    # Invoices and payments
    path('invoices/', views.invoices, name='invoices'),
    path('payments/', views.payments, name='payments'),
    
    # Payment processing with Stripe
    path('setup-intent/', views.create_setup_intent, name='create_setup_intent'),
    path('payment-method/add/', views.add_payment_method, name='add_payment_method'),
    
    # Stripe webhooks
    path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),
]