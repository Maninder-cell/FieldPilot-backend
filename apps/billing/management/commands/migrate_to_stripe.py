"""
Management command to migrate existing subscriptions to Stripe.

This script:
1. Creates Stripe customers for all tenants
2. Creates Stripe subscriptions for active subscriptions
3. Updates local records with Stripe IDs

Usage:
    python manage.py migrate_to_stripe [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.billing.models import Subscription
from apps.billing.stripe_service import StripeService, STRIPE_ENABLED
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing subscriptions to Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run migration in dry-run mode (no changes made)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY-RUN mode - no changes will be made'))
        
        if not STRIPE_ENABLED:
            self.stdout.write(self.style.ERROR('Stripe is not enabled. Please configure STRIPE_SECRET_KEY.'))
            return
        
        # Get subscriptions that need migration (no Stripe IDs)
        subscriptions_to_migrate = Subscription.objects.filter(
            stripe_subscription_id__isnull=True
        ) | Subscription.objects.filter(
            stripe_subscription_id=''
        )
        
        total_count = subscriptions_to_migrate.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No subscriptions need migration'))
            return
        
        self.stdout.write(f'Found {total_count} subscriptions to migrate')
        
        success_count = 0
        error_count = 0
        
        for subscription in subscriptions_to_migrate:
            tenant = subscription.tenant
            
            self.stdout.write(f'\nMigrating subscription for tenant: {tenant.name} (ID: {tenant.id})')
            
            try:
                # Get tenant owner for customer creation
                owner_membership = tenant.tenant_memberships.filter(
                    role='owner',
                    is_active=True
                ).first()
                
                if not owner_membership:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ No owner found for tenant {tenant.name}, skipping'
                    ))
                    error_count += 1
                    continue
                
                user = owner_membership.user
                
                if dry_run:
                    self.stdout.write(f'  [DRY-RUN] Would create Stripe customer for: {user.email}')
                    self.stdout.write(f'  [DRY-RUN] Would create Stripe subscription for plan: {subscription.plan.name}')
                    success_count += 1
                    continue
                
                with transaction.atomic():
                    # Step 1: Create or get Stripe customer
                    self.stdout.write(f'  Creating Stripe customer for: {user.email}')
                    customer = StripeService.get_or_create_customer(tenant, user)
                    customer_id = customer.id
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Stripe customer created: {customer_id}'))
                    
                    # Step 2: Determine billing cycle (default to monthly if not set)
                    billing_cycle = 'monthly'  # Default since we removed the field
                    
                    # Step 3: Get price ID
                    price_id = subscription.plan.stripe_price_id_monthly
                    if not price_id:
                        self.stdout.write(self.style.ERROR(
                            f'  ✗ No Stripe price ID configured for plan {subscription.plan.name}'
                        ))
                        error_count += 1
                        continue
                    
                    # Step 4: Determine trial end
                    trial_end = None
                    if tenant.is_trial_active:
                        trial_end = tenant.trial_ends_at
                        self.stdout.write(f'  Trial active until: {trial_end}')
                    
                    # Step 5: Create Stripe subscription
                    # Note: This requires a payment method. For migration, we'll create
                    # subscriptions in trial mode or with a default payment method if available
                    self.stdout.write(f'  Creating Stripe subscription for plan: {subscription.plan.name}')
                    
                    # For migration, we need to handle the case where there's no payment method
                    # We'll create the subscription with trial or skip if no trial
                    if not trial_end:
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠ Cannot create subscription without payment method and no active trial. '
                            f'Tenant needs to add payment method manually.'
                        ))
                        # Still update customer ID
                        subscription.stripe_customer_id = customer_id
                        subscription.save(update_fields=['stripe_customer_id', 'updated_at'])
                        error_count += 1
                        continue
                    
                    # Create subscription with trial (no payment method required during trial)
                    import stripe
                    stripe_subscription = stripe.Subscription.create(
                        customer=customer_id,
                        items=[{'price': price_id}],
                        trial_end=int(trial_end.timestamp()) if trial_end else None,
                        metadata={
                            'tenant_id': str(tenant.id),
                            'tenant_name': tenant.name,
                            'plan_id': str(subscription.plan.id),
                            'migrated': 'true'
                        }
                    )
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Stripe subscription created: {stripe_subscription.id}'
                    ))
                    
                    # Step 6: Update local subscription record
                    subscription.stripe_customer_id = customer_id
                    subscription.stripe_subscription_id = stripe_subscription.id
                    subscription.status = stripe_subscription.status
                    subscription.save()
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Local subscription updated with Stripe IDs'
                    ))
                    
                    success_count += 1
                    
            except Exception as e:
                logger.error(f'Error migrating subscription for tenant {tenant.name}: {str(e)}', exc_info=True)
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error: {str(e)}'
                ))
                error_count += 1
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Migration complete!'))
        self.stdout.write(f'Total subscriptions: {total_count}')
        self.stdout.write(self.style.SUCCESS(f'Successfully migrated: {success_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
        self.stdout.write('='*60)
