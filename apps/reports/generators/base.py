"""
Base Report Generator

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from abc import ABC, abstractmethod
from datetime import datetime, date
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
import logging

from apps.reports.utils import generate_cache_key, serialize_for_json

logger = logging.getLogger(__name__)


class BaseReportGenerator(ABC):
    """
    Abstract base class for all report generators.
    
    All report generators must inherit from this class and implement
    the required abstract methods.
    """
    
    # Report metadata (must be set by subclasses)
    report_type: str = None
    report_name: str = None
    cache_ttl: int = 3600  # Cache TTL in seconds (default: 1 hour)
    
    def __init__(self, user, filters=None):
        """
        Initialize the report generator.
        
        Args:
            user: User generating the report
            filters: Dictionary of filters to apply
        """
        if not self.report_type or not self.report_name:
            raise NotImplementedError(
                "Subclasses must define report_type and report_name"
            )
        
        self.user = user
        self.filters = filters or {}
        self.validate_filters()
    
    def validate_filters(self):
        """
        Validate the provided filters.
        Override in subclasses to add custom validation.
        """
        # Parse and validate date filters
        if 'start_date' in self.filters:
            self.filters['start_date'] = self._parse_date(self.filters['start_date'])
        
        if 'end_date' in self.filters:
            self.filters['end_date'] = self._parse_date(self.filters['end_date'])
        
        # Validate date range
        if 'start_date' in self.filters and 'end_date' in self.filters:
            if self.filters['start_date'] > self.filters['end_date']:
                raise ValueError("start_date must be before end_date")
    
    def _parse_date(self, date_value):
        """
        Parse date from string or return as-is if already a date object.
        
        Args:
            date_value: Date string (YYYY-MM-DD) or date object
            
        Returns:
            date object
        """
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError(f"Invalid date format: {date_value}. Use YYYY-MM-DD")
        elif isinstance(date_value, datetime):
            return date_value.date()
        elif isinstance(date_value, date):
            return date_value
        else:
            raise ValueError(f"Invalid date type: {type(date_value)}")
    
    @abstractmethod
    def get_queryset(self):
        """
        Get the base queryset for the report.
        Must be implemented by subclasses.
        
        Returns:
            Django QuerySet
        """
        raise NotImplementedError("Subclasses must implement get_queryset()")
    
    @abstractmethod
    def calculate_metrics(self, queryset):
        """
        Calculate metrics from the queryset.
        Must be implemented by subclasses.
        
        Args:
            queryset: Django QuerySet
            
        Returns:
            Dictionary of calculated metrics
        """
        raise NotImplementedError("Subclasses must implement calculate_metrics()")
    
    def format_data(self, data):
        """
        Format data for output.
        Override in subclasses to customize formatting.
        
        Args:
            data: Raw data dictionary
            
        Returns:
            Formatted data dictionary
        """
        return self._serialize_data(data)
    
    def _serialize_data(self, data):
        """
        Recursively serialize data for JSON output.
        
        Args:
            data: Data to serialize
            
        Returns:
            JSON-serializable data
        """
        if isinstance(data, dict):
            return {key: self._serialize_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, (datetime, date)):
            return data.isoformat()
        elif isinstance(data, Decimal):
            return float(data)
        elif hasattr(data, '__dict__'):
            return self._serialize_data(data.__dict__)
        else:
            return data
    
    def generate(self, use_cache=True):
        """
        Generate the report.
        
        Args:
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary containing report data
        """
        # Check cache if enabled
        if use_cache:
            cache_key = generate_cache_key(self.report_type, self.filters)
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Report {self.report_type} served from cache")
                return cached_data
        
        # Generate report
        logger.info(f"Generating report {self.report_type} with filters: {self.filters}")
        
        try:
            # Get queryset
            queryset = self.get_queryset()
            
            # Calculate metrics
            metrics = self.calculate_metrics(queryset)
            
            # Format data
            formatted_data = self.format_data(metrics)
            
            # Build report structure
            report_data = {
                'report_type': self.report_type,
                'report_name': self.report_name,
                'generated_at': timezone.now().isoformat(),
                'generated_by': {
                    'id': str(self.user.id),
                    'name': self.user.full_name,
                    'email': self.user.email,
                },
                'filters': self.filters,
                'data': formatted_data,
            }
            
            # Cache the result
            if use_cache:
                cache_key = generate_cache_key(self.report_type, self.filters)
                cache.set(cache_key, report_data, self.cache_ttl)
                logger.info(f"Report {self.report_type} cached with TTL {self.cache_ttl}s")
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating report {self.report_type}: {str(e)}", exc_info=True)
            raise
    
    def get_filter_value(self, key, default=None):
        """
        Get a filter value with a default.
        
        Args:
            key: Filter key
            default: Default value if key not found
            
        Returns:
            Filter value or default
        """
        return self.filters.get(key, default)
    
    def apply_date_filter(self, queryset, field_name='created_at'):
        """
        Apply date range filters to a queryset.
        
        Args:
            queryset: Django QuerySet
            field_name: Name of the date field to filter on
            
        Returns:
            Filtered QuerySet
        """
        if 'start_date' in self.filters:
            filter_kwargs = {f'{field_name}__gte': self.filters['start_date']}
            queryset = queryset.filter(**filter_kwargs)
        
        if 'end_date' in self.filters:
            filter_kwargs = {f'{field_name}__lte': self.filters['end_date']}
            queryset = queryset.filter(**filter_kwargs)
        
        return queryset
    
    def apply_status_filter(self, queryset, field_name='status'):
        """
        Apply status filter to a queryset.
        
        Args:
            queryset: Django QuerySet
            field_name: Name of the status field
            
        Returns:
            Filtered QuerySet
        """
        status_filter = self.get_filter_value('status')
        if status_filter:
            if isinstance(status_filter, list):
                filter_kwargs = {f'{field_name}__in': status_filter}
            else:
                filter_kwargs = {field_name: status_filter}
            queryset = queryset.filter(**filter_kwargs)
        
        return queryset
    
    def apply_priority_filter(self, queryset, field_name='priority'):
        """
        Apply priority filter to a queryset.
        
        Args:
            queryset: Django QuerySet
            field_name: Name of the priority field
            
        Returns:
            Filtered QuerySet
        """
        priority_filter = self.get_filter_value('priority')
        if priority_filter:
            if isinstance(priority_filter, list):
                filter_kwargs = {f'{field_name}__in': priority_filter}
            else:
                filter_kwargs = {field_name: priority_filter}
            queryset = queryset.filter(**filter_kwargs)
        
        return queryset
    
    def get_metadata(self):
        """
        Get report metadata.
        
        Returns:
            Dictionary of report metadata
        """
        return {
            'report_type': self.report_type,
            'report_name': self.report_name,
            'cache_ttl': self.cache_ttl,
        }
