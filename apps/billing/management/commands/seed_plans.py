"""
Seed subscription plans

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.management.base import BaseCommand
from apps.billing.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Seed subscription plans'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': 'Starter',
                'slug': 'starter',
                'description': 'Perfect for small teams getting started with field service management',
                'price_monthly': 29.00,
                'price_yearly': 290.00,
                'max_users': 5,
                'max_equipment': 50,
                'max_storage_gb': 5,
                'max_api_calls_per_month': 10000,
                'features': {
                    'equipment_management': True,
                    'task_scheduling': True,
                    'basic_reporting': True,
                    'mobile_app': True,
                    'email_support': True,
                    'custom_fields': False,
                    'advanced_analytics': False,
                    'api_access': False,
                    'priority_support': False,
                    'custom_integrations': False,
                },
                'sort_order': 1,
            },
            {
                'name': 'Professional',
                'slug': 'professional',
                'description': 'For growing businesses that need advanced features and more capacity',
                'price_monthly': 79.00,
                'price_yearly': 790.00,
                'max_users': 25,
                'max_equipment': 250,
                'max_storage_gb': 25,
                'max_api_calls_per_month': 50000,
                'features': {
                    'equipment_management': True,
                    'task_scheduling': True,
                    'basic_reporting': True,
                    'mobile_app': True,
                    'email_support': True,
                    'custom_fields': True,
                    'advanced_analytics': True,
                    'api_access': True,
                    'priority_support': False,
                    'custom_integrations': False,
                    'maintenance_scheduling': True,
                    'inventory_management': True,
                },
                'sort_order': 2,
            },
            {
                'name': 'Enterprise',
                'slug': 'enterprise',
                'description': 'For large organizations requiring unlimited capacity and premium support',
                'price_monthly': 199.00,
                'price_yearly': 1990.00,
                'max_users': None,  # Unlimited
                'max_equipment': None,
                'max_storage_gb': None,
                'max_api_calls_per_month': None,
                'features': {
                    'equipment_management': True,
                    'task_scheduling': True,
                    'basic_reporting': True,
                    'mobile_app': True,
                    'email_support': True,
                    'custom_fields': True,
                    'advanced_analytics': True,
                    'api_access': True,
                    'priority_support': True,
                    'custom_integrations': True,
                    'maintenance_scheduling': True,
                    'inventory_management': True,
                    'dedicated_account_manager': True,
                    'sla_guarantee': True,
                    'white_label': True,
                },
                'sort_order': 3,
            },
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=plan_data['slug'],
                defaults=plan_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created plan: {plan.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated plan: {plan.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSeeding complete! Created: {created_count}, Updated: {updated_count}'
            )
        )
