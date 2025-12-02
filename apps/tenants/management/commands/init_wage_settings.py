"""
Management command to initialize wage and working hour settings for existing tenants.

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from apps.tenants.models import Tenant, TenantSettings


class Command(BaseCommand):
    help = 'Initialize wage and working hour settings for all existing tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--normal-hours',
            type=float,
            default=8.0,
            help='Normal working hours per day (default: 8.0)'
        )
        parser.add_argument(
            '--normal-rate',
            type=float,
            default=50.0,
            help='Default normal hourly rate (default: 50.0)'
        )
        parser.add_argument(
            '--overtime-rate',
            type=float,
            default=75.0,
            help='Default overtime hourly rate (default: 75.0)'
        )
        parser.add_argument(
            '--currency',
            type=str,
            default='USD',
            help='Currency code (default: USD)'
        )

    def handle(self, *args, **options):
        normal_hours = options['normal_hours']
        normal_rate = options['normal_rate']
        overtime_rate = options['overtime_rate']
        currency = options['currency']

        self.stdout.write(self.style.SUCCESS('Initializing wage settings for all tenants...'))
        self.stdout.write(f'  Normal working hours: {normal_hours} hours/day')
        self.stdout.write(f'  Normal hourly rate: {currency} {normal_rate}')
        self.stdout.write(f'  Overtime hourly rate: {currency} {overtime_rate}')
        self.stdout.write('')

        # Get all tenants
        tenants = Tenant.objects.all()
        updated_count = 0
        created_count = 0

        for tenant in tenants:
            # Switch to tenant schema
            connection.set_tenant(tenant)
            
            # Get or create tenant settings
            settings, created = TenantSettings.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'normal_working_hours_per_day': normal_hours,
                    'default_normal_hourly_rate': normal_rate,
                    'default_overtime_hourly_rate': overtime_rate,
                    'currency': currency,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created settings for tenant: {tenant.name}')
                )
            else:
                # Update existing settings if they have default values
                updated = False
                if settings.normal_working_hours_per_day == 8.0:
                    settings.normal_working_hours_per_day = normal_hours
                    updated = True
                if settings.default_normal_hourly_rate == 50.0:
                    settings.default_normal_hourly_rate = normal_rate
                    updated = True
                if settings.default_overtime_hourly_rate == 75.0:
                    settings.default_overtime_hourly_rate = overtime_rate
                    updated = True
                if settings.currency == 'USD':
                    settings.currency = currency
                    updated = True
                
                if updated:
                    settings.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'⟳ Updated settings for tenant: {tenant.name}')
                    )
                else:
                    self.stdout.write(f'  Skipped tenant (already configured): {tenant.name}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Done! Created: {created_count}, Updated: {updated_count}'))
