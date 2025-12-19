"""
Celery Tasks for File Management

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from celery import shared_task
from apps.tenants.models import Tenant
from .storage import StorageManager
import logging

logger = logging.getLogger(__name__)


@shared_task(name='files.cleanup_old_files')
def cleanup_old_files_task(days_old=30):
    """
    Celery task to cleanup old soft-deleted files for all tenants.
    
    Args:
        days_old: Delete files soft-deleted more than this many days ago
    """
    logger.info(f"Starting cleanup of files deleted more than {days_old} days ago")
    
    tenants = Tenant.objects.exclude(schema_name='public')
    total_files = 0
    total_bytes = 0
    
    for tenant in tenants:
        try:
            count, bytes_freed = StorageManager.cleanup_deleted_files(tenant, days_old)
            total_files += count
            total_bytes += bytes_freed
            
            if count > 0:
                mb_freed = round(bytes_freed / (1024 * 1024), 2)
                logger.info(f"Tenant {tenant.schema_name}: Cleaned up {count} files, freed {mb_freed}MB")
        except Exception as e:
            logger.error(f"Error cleaning up files for tenant {tenant.schema_name}: {str(e)}")
    
    total_mb = round(total_bytes / (1024 * 1024), 2)
    logger.info(f"Cleanup complete. Total: {total_files} files, {total_mb}MB freed")
    
    return {
        'total_files': total_files,
        'total_bytes': total_bytes,
        'total_mb': total_mb,
    }


@shared_task(name='files.generate_storage_report')
def generate_storage_report_task():
    """
    Generate storage usage report for all tenants.
    """
    logger.info("Generating storage usage report")
    
    tenants = Tenant.objects.exclude(schema_name='public')
    report = []
    
    for tenant in tenants:
        try:
            stats = StorageManager.get_storage_stats(tenant)
            report.append({
                'tenant': tenant.schema_name,
                'usage_gb': stats['usage_gb'],
                'limit_gb': stats['limit_gb'],
                'percentage_used': stats['percentage_used'],
                'is_quota_exceeded': stats['is_quota_exceeded'],
            })
            
            # Log warning if quota exceeded
            if stats['is_quota_exceeded']:
                logger.warning(
                    f"Tenant {tenant.schema_name} has exceeded storage quota: "
                    f"{stats['usage_gb']}GB / {stats['limit_gb']}GB"
                )
        except Exception as e:
            logger.error(f"Error generating report for tenant {tenant.schema_name}: {str(e)}")
    
    return report


@shared_task(name='files.check_storage_quotas')
def check_storage_quotas_task():
    """
    Check storage quotas for all tenants and send alerts if needed.
    """
    logger.info("Checking storage quotas for all tenants")
    
    tenants = Tenant.objects.exclude(schema_name='public')
    alerts = []
    
    for tenant in tenants:
        try:
            stats = StorageManager.get_storage_stats(tenant)
            
            # Alert if over 90% usage
            if not stats['is_unlimited'] and stats['percentage_used'] >= 90:
                alert = {
                    'tenant': tenant.schema_name,
                    'usage_gb': stats['usage_gb'],
                    'limit_gb': stats['limit_gb'],
                    'percentage_used': stats['percentage_used'],
                    'is_exceeded': stats['is_quota_exceeded'],
                }
                alerts.append(alert)
                
                logger.warning(
                    f"Storage alert for tenant {tenant.schema_name}: "
                    f"{stats['percentage_used']}% used ({stats['usage_gb']}GB / {stats['limit_gb']}GB)"
                )
                
                # TODO: Send email notification to tenant admins
        except Exception as e:
            logger.error(f"Error checking quota for tenant {tenant.schema_name}: {str(e)}")
    
    return alerts
