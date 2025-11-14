"""
Report Generators

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from .base import BaseReportGenerator

# Import all generator modules to register them
from . import task_reports
from . import equipment_reports
from . import technician_reports
from . import service_request_reports
from . import financial_reports

__all__ = ['BaseReportGenerator']
