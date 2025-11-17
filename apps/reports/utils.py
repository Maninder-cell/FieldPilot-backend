"""
Reports Utilities

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import hashlib
import json
from datetime import datetime, date
from decimal import Decimal


def generate_cache_key(report_type, filters):
    """
    Generate a cache key from report type and filters.
    
    Args:
        report_type: Type of report
        filters: Dictionary of filters
        
    Returns:
        Cache key string
    """
    # Sort filters for consistent hashing
    sorted_filters = json.dumps(filters, sort_keys=True, default=str)
    filter_hash = hashlib.md5(sorted_filters.encode()).hexdigest()
    
    return f"report:{report_type}:{filter_hash}"


def serialize_for_json(obj):
    """
    Serialize objects for JSON output.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-serializable value
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)


def format_duration(seconds):
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m")
    """
    if seconds is None:
        return None
        
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def calculate_percentage(part, total):
    """
    Calculate percentage with safe division.
    
    Args:
        part: Part value
        total: Total value
        
    Returns:
        Percentage as float, or 0 if total is 0
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)
