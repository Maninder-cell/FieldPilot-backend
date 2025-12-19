"""
Management command to cleanup old deleted files

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.management.base import BaseCommand
from apps.tenants.models import Tenant
from apps.files.storage import StorageManager


class Command(BaseCommand):
    help = 'Cleanup old soft-deleted files for all tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete files soft-deleted more than this many days ago (default: 30)'
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Cleanup for specific tenant schema name (optional)'
        )
    
    def handle(self, *args, **options):
        days_old = options['days']
        tenant_filter = options.get('tenant')
        
        self.stdout.write(self.style.SUCCESS(
            f'Starting cleanup of files deleted more than {days_old} days ago...'
        ))
        
        # Get tenants to process
        if tenant_filter:
            tenants = Tenant.objects.filter(schema_name=tenant_filter)
        else:
            tenants = Tenant.objects.exclude(schema_name='public')
        
        total_files = 0
        total_bytes = 0
        
        for tenant in tenants:
            self.stdout.write(f'Processing tenant: {tenant.schema_name}...')
            
            try:
                count, bytes_freed = StorageManager.cleanup_deleted_files(tenant, days_old)
                total_files += count
                total_bytes += bytes_freed
                
                if count > 0:
                    mb_freed = round(bytes_freed / (1024 * 1024), 2)
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Cleaned up {count} files, freed {mb_freed}MB'
                    ))
                else:
                    self.stdout.write('  - No files to cleanup')
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error: {str(e)}'
                ))
        
        # Summary
        total_mb = round(total_bytes / (1024 * 1024), 2)
        total_gb = round(total_bytes / (1024 * 1024 * 1024), 2)
        
        self.stdout.write(self.style.SUCCESS(
            f'\nCleanup complete!'
        ))
        self.stdout.write(f'Total files deleted: {total_files}')
        self.stdout.write(f'Total space freed: {total_mb}MB ({total_gb}GB)')
