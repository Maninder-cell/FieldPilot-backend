"""
Custom Pagination Classes

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination class that allows clients to set page size via query parameter.
    """
    page_size = 10  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override page size
    max_page_size = 100  # Maximum allowed page size
