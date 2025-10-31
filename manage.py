#!/usr/bin/env python
"""
FieldPilot Django Management Script

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import os
import sys

def main():
    """Run administrative tasks."""
    # Load .env file first
    try:
        from decouple import config
        settings_module = config('DJANGO_SETTINGS_MODULE', default='config.settings_dev')
        os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    except ImportError:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_dev')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()