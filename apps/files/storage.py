"""
Storage Management and Quota Tracking

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class StorageQuotaExceeded(Exception):
    """Exception raised when storage quota is exceeded."""
    pass


class StorageManager:
    """
    Manages storage quota and usage tracking for tenants.
    """
    
    @staticmethod
    def get_tenant_storage_limit_bytes(tenant):
        """
        Get storage limit in bytes for a tenant based on their subscription.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            int: Storage limit in bytes, or None for unlimited
        """
        try:
            subscription = tenant.subscription
            if subscription and subscription.plan:
                max_storage_gb = subscription.plan.max_storage_gb
                if max_storage_gb:
                    # Convert GB to bytes
                    return max_storage_gb * 1024 * 1024 * 1024
            return None  # Unlimited
        except Exception as e:
            logger.error(f"Error getting storage limit for tenant {tenant.id}: {str(e)}")
            return None
    
    @staticmethod
    def get_tenant_storage_usage_bytes(tenant):
        """
        Calculate total storage used by a tenant across all files.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            int: Total storage used in bytes
        """
        from apps.files.models import UserFile
        from django_tenants.utils import schema_context
        
        try:
            with schema_context(tenant.schema_name):
                total = UserFile.objects.filter(
                    deleted_at__isnull=True
                ).aggregate(
                    total_size=Sum('file_size')
                )['total_size'] or 0
                return total
        except Exception as e:
            logger.error(f"Error calculating storage usage for tenant {tenant.id}: {str(e)}")
            return 0
    
    @staticmethod
    def get_storage_stats(tenant):
        """
        Get comprehensive storage statistics for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: Storage statistics
        """
        usage_bytes = StorageManager.get_tenant_storage_usage_bytes(tenant)
        limit_bytes = StorageManager.get_tenant_storage_limit_bytes(tenant)
        
        # Convert to human-readable formats
        usage_mb = round(usage_bytes / (1024 * 1024), 2)
        usage_gb = round(usage_bytes / (1024 * 1024 * 1024), 2)
        
        stats = {
            'usage_bytes': usage_bytes,
            'usage_mb': usage_mb,
            'usage_gb': usage_gb,
            'limit_bytes': limit_bytes,
            'limit_gb': limit_bytes / (1024 * 1024 * 1024) if limit_bytes else None,
            'is_unlimited': limit_bytes is None,
            'percentage_used': 0,
            'remaining_bytes': None,
            'remaining_gb': None,
            'is_quota_exceeded': False,
            'can_upload': True,
        }
        
        if limit_bytes:
            stats['percentage_used'] = round((usage_bytes / limit_bytes) * 100, 2)
            stats['remaining_bytes'] = max(0, limit_bytes - usage_bytes)
            stats['remaining_gb'] = round(stats['remaining_bytes'] / (1024 * 1024 * 1024), 2)
            stats['is_quota_exceeded'] = usage_bytes >= limit_bytes
            stats['can_upload'] = usage_bytes < limit_bytes
        
        return stats
    
    @staticmethod
    def check_upload_allowed(tenant, file_size):
        """
        Check if a file upload is allowed based on storage quota.
        
        Args:
            tenant: Tenant instance
            file_size: Size of file to upload in bytes
            
        Returns:
            tuple: (allowed: bool, message: str, stats: dict)
        """
        stats = StorageManager.get_storage_stats(tenant)
        
        # If unlimited storage, always allow
        if stats['is_unlimited']:
            return True, "Upload allowed", stats
        
        # Check if already over quota
        if stats['is_quota_exceeded']:
            return False, f"Storage quota exceeded. Used {stats['usage_gb']}GB of {stats['limit_gb']}GB.", stats
        
        # Check if this upload would exceed quota
        new_usage = stats['usage_bytes'] + file_size
        if new_usage > stats['limit_bytes']:
            remaining_mb = round(stats['remaining_bytes'] / (1024 * 1024), 2)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            return False, f"Upload would exceed storage quota. {remaining_mb}MB remaining, file is {file_size_mb}MB.", stats
        
        return True, "Upload allowed", stats
    
    @staticmethod
    def validate_file_upload(tenant, file_size):
        """
        Validate if file upload is allowed, raise exception if not.
        
        Args:
            tenant: Tenant instance
            file_size: Size of file to upload in bytes
            
        Raises:
            StorageQuotaExceeded: If upload would exceed quota
        """
        allowed, message, stats = StorageManager.check_upload_allowed(tenant, file_size)
        
        if not allowed:
            logger.warning(f"Storage quota check failed for tenant {tenant.id}: {message}")
            raise StorageQuotaExceeded(message)
        
        logger.info(f"Storage quota check passed for tenant {tenant.id}. Usage: {stats['usage_gb']}GB / {stats['limit_gb']}GB")
    
    @staticmethod
    def get_file_count_by_type(tenant):
        """
        Get count of files by type for a tenant.
        
        Args:
            tenant: Tenant instance
            
        Returns:
            dict: File counts by type
        """
        from apps.files.models import UserFile
        from django_tenants.utils import schema_context
        from django.db.models import Count
        
        try:
            with schema_context(tenant.schema_name):
                counts = UserFile.objects.filter(
                    deleted_at__isnull=True
                ).values('file_type').annotate(
                    count=Count('id'),
                    total_size=Sum('file_size')
                ).order_by('-total_size')
                
                return {
                    item['file_type']: {
                        'count': item['count'],
                        'total_size_bytes': item['total_size'],
                        'total_size_mb': round(item['total_size'] / (1024 * 1024), 2)
                    }
                    for item in counts
                }
        except Exception as e:
            logger.error(f"Error getting file counts for tenant {tenant.id}: {str(e)}")
            return {}
    
    @staticmethod
    def get_largest_files(tenant, limit=10):
        """
        Get largest files for a tenant.
        
        Args:
            tenant: Tenant instance
            limit: Number of files to return
            
        Returns:
            QuerySet: Largest files
        """
        from apps.files.models import UserFile
        from django_tenants.utils import schema_context
        
        try:
            with schema_context(tenant.schema_name):
                return UserFile.objects.filter(
                    deleted_at__isnull=True
                ).order_by('-file_size')[:limit]
        except Exception as e:
            logger.error(f"Error getting largest files for tenant {tenant.id}: {str(e)}")
            return []
    
    @staticmethod
    def cleanup_deleted_files(tenant, days_old=30):
        """
        Permanently delete soft-deleted files older than specified days.
        
        Args:
            tenant: Tenant instance
            days_old: Delete files soft-deleted more than this many days ago
            
        Returns:
            tuple: (count: int, bytes_freed: int)
        """
        from apps.files.models import UserFile
        from django_tenants.utils import schema_context
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        try:
            with schema_context(tenant.schema_name):
                old_files = UserFile.objects.filter(
                    deleted_at__isnull=False,
                    deleted_at__lt=cutoff_date
                )
                
                count = old_files.count()
                bytes_freed = old_files.aggregate(
                    total=Sum('file_size')
                )['total'] or 0
                
                # Permanently delete
                for file in old_files:
                    file.delete()  # This will also delete the physical file
                
                logger.info(f"Cleaned up {count} files for tenant {tenant.id}, freed {bytes_freed} bytes")
                return count, bytes_freed
        except Exception as e:
            logger.error(f"Error cleaning up files for tenant {tenant.id}: {str(e)}")
            return 0, 0
