"""
Report Registry

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import logging

logger = logging.getLogger(__name__)


class ReportRegistry:
    """
    Registry for managing available report types and their generators.
    """
    
    def __init__(self):
        self._generators = {}
    
    def register(self, report_type, generator_class):
        """
        Register a report generator.
        
        Args:
            report_type: Unique identifier for the report type
            generator_class: Generator class (must inherit from BaseReportGenerator)
        """
        from apps.reports.generators.base import BaseReportGenerator
        
        if not issubclass(generator_class, BaseReportGenerator):
            raise ValueError(
                f"Generator class must inherit from BaseReportGenerator, "
                f"got {generator_class}"
            )
        
        if report_type in self._generators:
            logger.warning(f"Overwriting existing generator for report type: {report_type}")
        
        self._generators[report_type] = generator_class
        logger.info(f"Registered report generator: {report_type} -> {generator_class.__name__}")
    
    def unregister(self, report_type):
        """
        Unregister a report generator.
        
        Args:
            report_type: Report type to unregister
        """
        if report_type in self._generators:
            del self._generators[report_type]
            logger.info(f"Unregistered report generator: {report_type}")
    
    def get_generator_class(self, report_type):
        """
        Get the generator class for a report type.
        
        Args:
            report_type: Report type identifier
            
        Returns:
            Generator class
            
        Raises:
            KeyError: If report type is not registered
        """
        if report_type not in self._generators:
            raise KeyError(f"Unknown report type: {report_type}")
        
        return self._generators[report_type]
    
    def create_generator(self, report_type, user, filters=None):
        """
        Create a generator instance for a report type.
        
        Args:
            report_type: Report type identifier
            user: User generating the report
            filters: Filters to apply
            
        Returns:
            Generator instance
            
        Raises:
            KeyError: If report type is not registered
        """
        generator_class = self.get_generator_class(report_type)
        return generator_class(user, filters)
    
    def list_report_types(self):
        """
        List all registered report types.
        
        Returns:
            List of dictionaries with report type information
        """
        report_types = []
        
        for report_type, generator_class in self._generators.items():
            # Create a temporary instance to get metadata
            try:
                # Get class-level attributes without instantiation
                report_types.append({
                    'report_type': report_type,
                    'report_name': generator_class.report_name,
                    'description': generator_class.__doc__.strip() if generator_class.__doc__ else '',
                    'generator_class': generator_class.__name__,
                })
            except Exception as e:
                logger.error(f"Error getting metadata for {report_type}: {str(e)}")
                report_types.append({
                    'report_type': report_type,
                    'report_name': report_type,
                    'description': '',
                    'generator_class': generator_class.__name__,
                })
        
        return sorted(report_types, key=lambda x: x['report_name'])
    
    def is_registered(self, report_type):
        """
        Check if a report type is registered.
        
        Args:
            report_type: Report type identifier
            
        Returns:
            bool: True if registered, False otherwise
        """
        return report_type in self._generators
    
    def get_report_info(self, report_type):
        """
        Get detailed information about a report type.
        
        Args:
            report_type: Report type identifier
            
        Returns:
            Dictionary with report information
            
        Raises:
            KeyError: If report type is not registered
        """
        generator_class = self.get_generator_class(report_type)
        
        return {
            'report_type': report_type,
            'report_name': generator_class.report_name,
            'description': generator_class.__doc__.strip() if generator_class.__doc__ else '',
            'generator_class': generator_class.__name__,
            'cache_ttl': generator_class.cache_ttl,
            'available_filters': self._get_available_filters(generator_class),
        }
    
    def _get_available_filters(self, generator_class):
        """
        Get available filters for a generator class.
        
        Args:
            generator_class: Generator class
            
        Returns:
            List of available filter names
        """
        # This is a basic implementation
        # Subclasses can define a class attribute 'available_filters'
        if hasattr(generator_class, 'available_filters'):
            return generator_class.available_filters
        
        # Default filters that most reports support
        return [
            'start_date',
            'end_date',
            'status',
            'priority',
        ]


# Global registry instance
registry = ReportRegistry()


def register_report(report_type):
    """
    Decorator to register a report generator.
    
    Usage:
        @register_report('task_summary')
        class TaskSummaryReportGenerator(BaseReportGenerator):
            ...
    
    Args:
        report_type: Unique identifier for the report type
    """
    def decorator(generator_class):
        registry.register(report_type, generator_class)
        return generator_class
    return decorator


def get_generator(report_type, user, filters=None):
    """
    Convenience function to create a generator instance.
    
    Args:
        report_type: Report type identifier
        user: User generating the report
        filters: Filters to apply
        
    Returns:
        Generator instance
    """
    return registry.create_generator(report_type, user, filters)


def list_reports():
    """
    Convenience function to list all available reports.
    
    Returns:
        List of report type information
    """
    return registry.list_report_types()


def get_report_info(report_type):
    """
    Convenience function to get report information.
    
    Args:
        report_type: Report type identifier
        
    Returns:
        Dictionary with report information
    """
    return registry.get_report_info(report_type)
