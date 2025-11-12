"""
Service Request Caching Utilities

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ServiceRequestCache:
    """
    Caching utilities for service requests.
    Task 20.2: Implement caching
    """
    
    # Cache timeouts (in seconds)
    DASHBOARD_CACHE_TIMEOUT = 5 * 60  # 5 minutes
    EQUIPMENT_LIST_CACHE_TIMEOUT = 10 * 60  # 10 minutes
    METRICS_CACHE_TIMEOUT = 15 * 60  # 15 minutes
    
    @staticmethod
    def get_customer_dashboard_cache_key(customer_id):
        """Get cache key for customer dashboard."""
        return f"customer_dashboard:{customer_id}"
    
    @staticmethod
    def get_customer_equipment_cache_key(customer_id):
        """Get cache key for customer equipment list."""
        return f"customer_equipment:{customer_id}"
    
    @staticmethod
    def get_request_metrics_cache_key():
        """Get cache key for request metrics."""
        return "request_metrics:overview"
    
    @staticmethod
    def cache_customer_dashboard(customer_id, data):
        """
        Cache customer dashboard data.
        """
        cache_key = ServiceRequestCache.get_customer_dashboard_cache_key(customer_id)
        cache.set(cache_key, data, ServiceRequestCache.DASHBOARD_CACHE_TIMEOUT)
        logger.debug(f"Cached dashboard for customer {customer_id}")
    
    @staticmethod
    def get_cached_customer_dashboard(customer_id):
        """
        Get cached customer dashboard data.
        """
        cache_key = ServiceRequestCache.get_customer_dashboard_cache_key(customer_id)
        data = cache.get(cache_key)
        if data:
            logger.debug(f"Cache hit for dashboard: customer {customer_id}")
        return data
    
    @staticmethod
    def invalidate_customer_dashboard(customer_id):
        """
        Invalidate customer dashboard cache.
        """
        cache_key = ServiceRequestCache.get_customer_dashboard_cache_key(customer_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated dashboard cache for customer {customer_id}")
    
    @staticmethod
    def cache_customer_equipment(customer_id, data):
        """
        Cache customer equipment list.
        """
        cache_key = ServiceRequestCache.get_customer_equipment_cache_key(customer_id)
        cache.set(cache_key, data, ServiceRequestCache.EQUIPMENT_LIST_CACHE_TIMEOUT)
        logger.debug(f"Cached equipment list for customer {customer_id}")
    
    @staticmethod
    def get_cached_customer_equipment(customer_id):
        """
        Get cached customer equipment list.
        """
        cache_key = ServiceRequestCache.get_customer_equipment_cache_key(customer_id)
        data = cache.get(cache_key)
        if data:
            logger.debug(f"Cache hit for equipment: customer {customer_id}")
        return data
    
    @staticmethod
    def invalidate_customer_equipment(customer_id):
        """
        Invalidate customer equipment cache.
        """
        cache_key = ServiceRequestCache.get_customer_equipment_cache_key(customer_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated equipment cache for customer {customer_id}")
    
    @staticmethod
    def cache_request_metrics(data):
        """
        Cache request metrics.
        """
        cache_key = ServiceRequestCache.get_request_metrics_cache_key()
        cache.set(cache_key, data, ServiceRequestCache.METRICS_CACHE_TIMEOUT)
        logger.debug("Cached request metrics")
    
    @staticmethod
    def get_cached_request_metrics():
        """
        Get cached request metrics.
        """
        cache_key = ServiceRequestCache.get_request_metrics_cache_key()
        data = cache.get(cache_key)
        if data:
            logger.debug("Cache hit for request metrics")
        return data
    
    @staticmethod
    def invalidate_request_metrics():
        """
        Invalidate request metrics cache.
        """
        cache_key = ServiceRequestCache.get_request_metrics_cache_key()
        cache.delete(cache_key)
        logger.debug("Invalidated request metrics cache")
    
    @staticmethod
    def invalidate_all_customer_caches(customer_id):
        """
        Invalidate all caches for a customer.
        Call this when customer data changes.
        """
        ServiceRequestCache.invalidate_customer_dashboard(customer_id)
        ServiceRequestCache.invalidate_customer_equipment(customer_id)
        logger.info(f"Invalidated all caches for customer {customer_id}")


class QueryOptimizer:
    """
    Query optimization utilities.
    Task 20.1: Database optimization
    """
    
    @staticmethod
    def optimize_service_request_queryset(queryset):
        """
        Optimize service request queryset with select_related and prefetch_related.
        """
        return queryset.select_related(
            'customer',
            'equipment',
            'facility',
            'reviewed_by',
            'converted_task'
        ).prefetch_related(
            'attachments',
            'comments',
            'actions'
        )
    
    @staticmethod
    def optimize_equipment_queryset(queryset):
        """
        Optimize equipment queryset.
        """
        return queryset.select_related(
            'facility',
            'building',
            'customer'
        )
