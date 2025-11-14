# Reports Module

Comprehensive reporting system for FieldPilot facility management platform.

## Overview

The reports module provides powerful reporting capabilities across all aspects of the platform including tasks, equipment, technicians, service requests, and financial data. Reports can be generated in three formats: JSON (for web display), PDF (for printing), and Excel (for data analysis).

## Features

- **16 Report Types** across 5 categories
- **3 Export Formats**: JSON/HTML, PDF, Excel
- **Report Scheduling**: Automated report generation and email delivery
- **Caching**: Performance optimization with configurable TTL
- **Background Processing**: Async generation for large reports
- **Audit Logging**: Complete tracking of all report operations
- **Permission Control**: Admin and manager access only

## Available Reports

### Task Reports

1. **Task Summary** (`task_summary`)
   - Total tasks, completion rates, overdue tasks
   - Breakdown by status and priority
   - Average completion time

2. **Task Detail** (`task_detail`)
   - Detailed task information with equipment and assignments
   - Work hours and overtime tracking
   - Filterable and paginated

3. **Overdue Tasks** (`overdue_tasks`)
   - Tasks past scheduled end date
   - Days overdue calculation
   - Grouped by priority

### Equipment Reports

4. **Equipment Summary** (`equipment_summary`)
   - Total equipment counts by type, status, condition
   - Warranty expiration alerts

5. **Equipment Detail** (`equipment_detail`)
   - Complete equipment information
   - Building and facility associations

6. **Equipment Maintenance History** (`equipment_maintenance_history`)
   - Maintenance task history per equipment
   - Last maintenance date and frequency

7. **Equipment Utilization** (`equipment_utilization`)
   - Task counts per equipment
   - Most and least utilized equipment

### Technician Reports

8. **Technician Worksheet** (`technician_worksheet`)
   - Time logs with travel, arrival, departure times
   - Work hours, normal hours, overtime
   - Equipment status at departure

9. **Technician Performance** (`technician_performance`)
   - Completed tasks and work hours
   - Average task completion time
   - Customer ratings

10. **Technician Productivity** (`technician_productivity`)
    - Tasks per day
    - Hours per task
    - Efficiency metrics

11. **Team Performance** (`team_performance`)
    - Aggregated team metrics
    - Individual member contributions

12. **Overtime Report** (`overtime_report`)
    - Overtime hours by technician
    - Optional cost calculations

### Service Request Reports

13. **Service Request Summary** (`service_request_summary`)
    - Request counts by status, priority, type
    - Conversion rates and response times
    - Customer satisfaction metrics

14. **Service Request Detail** (`service_request_detail`)
    - Complete request information
    - Customer details and timeline
    - Converted task information

### Financial Reports

15. **Labor Cost** (`labor_cost`)
    - Labor costs by technician, task, customer
    - Configurable hourly rates
    - Normal vs overtime costs

16. **Materials Usage** (`materials_usage`)
    - Materials needed vs received
    - Breakdown by task and material type

17. **Customer Billing** (`customer_billing`)
    - Billable work aggregated by customer
    - Labor and material costs
    - Task breakdown

## API Endpoints

### Generate Report

```http
POST /api/v1/reports/generate/
```

**Request Body:**
```json
{
  "report_type": "task_summary",
  "filters": {
    "start_date": "2025-01-01",
    "end_date": "2025-01-31",
    "status": ["new", "in_progress"],
    "priority": ["high", "critical"]
  },
  "format": "json",
  "use_cache": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "report_type": "task_summary",
    "report_name": "Task Summary Report",
    "generated_at": "2025-01-15T10:30:00Z",
    "generated_by": {
      "id": "uuid",
      "name": "John Admin",
      "email": "john@example.com"
    },
    "filters": {...},
    "data": {
      "summary": {...},
      "by_status": {...},
      "by_priority": {...}
    }
  }
}
```

### Export Report

```http
GET /api/v1/reports/{report_id}/export/pdf/
GET /api/v1/reports/{report_id}/export/excel/
```

Returns file download with appropriate content type.

### List Report Types

```http
GET /api/v1/reports/types/
```

Returns list of all available report types with descriptions.

### Report Schedules

```http
GET    /api/v1/reports/schedules/
POST   /api/v1/reports/schedules/
GET    /api/v1/reports/schedules/{schedule_id}/
PUT    /api/v1/reports/schedules/{schedule_id}/
DELETE /api/v1/reports/schedules/{schedule_id}/
```

### Audit Logs

```http
GET /api/v1/reports/audit/
```

Query parameters: `report_type`, `status`, `user`, `page`, `page_size`

## Common Filters

Most reports support these filters:

- `start_date` (YYYY-MM-DD): Filter by start date
- `end_date` (YYYY-MM-DD): Filter by end date
- `status`: Filter by status (string or array)
- `priority`: Filter by priority (string or array)
- `equipment`: Filter by equipment ID
- `technician`: Filter by technician ID
- `customer`: Filter by customer ID
- `limit`: Pagination limit (default: 100)
- `offset`: Pagination offset (default: 0)

## Report Scheduling

Create automated reports that run on a schedule and are emailed to recipients.

**Create Schedule:**
```json
{
  "name": "Weekly Task Summary",
  "report_type": "task_summary",
  "filters": {
    "status": ["new", "in_progress"]
  },
  "format": "pdf",
  "frequency": "weekly",
  "day_of_week": 1,
  "time_of_day": "09:00:00",
  "recipients": ["manager@example.com"],
  "is_active": true
}
```

**Frequencies:**
- `daily`: Runs every day at specified time
- `weekly`: Runs on specified day of week (0=Monday, 6=Sunday)
- `monthly`: Runs on specified day of month (1-31)

## Usage Examples

### Python/Django

```python
from apps.reports.registry import get_generator

# Generate a report
generator = get_generator('task_summary', user, {
    'start_date': '2025-01-01',
    'end_date': '2025-01-31'
})
report_data = generator.generate()

# Export to PDF
from apps.reports.exporters.pdf_exporter import generate_pdf_report
pdf_bytes = generate_pdf_report(report_data, 'task_summary')

# Export to Excel
from apps.reports.exporters.excel_exporter import generate_excel_report
excel_bytes = generate_excel_report(report_data, 'task_summary')
```

### Celery Tasks

```python
from apps.reports.tasks import generate_report_async

# Generate report asynchronously
task = generate_report_async.delay(
    user_id=user.id,
    report_type='task_summary',
    filters={'start_date': '2025-01-01'},
    output_format='pdf'
)

# Check task status
result = task.get()
```

## Caching

Reports are cached by default with configurable TTL:

- Summary reports: 1 hour
- Detail reports: 30 minutes
- Financial reports: 1 hour

Cache keys are generated from report type and filters, ensuring unique caching per query.

To bypass cache:
```json
{
  "report_type": "task_summary",
  "use_cache": false
}
```

## Performance

- **Query Optimization**: All generators use `select_related()` and `prefetch_related()`
- **Pagination**: Detail reports support limit/offset pagination
- **Background Processing**: Large reports can be generated asynchronously
- **Caching**: Frequently accessed reports are cached

## Permissions

Only users with `admin` or `manager` roles can:
- Generate reports
- Export reports
- Create/manage schedules
- View audit logs

Enforced via `IsAdminOrManager` permission class.

## Audit Logging

All report operations are logged:

- Report generation attempts
- Execution time
- Success/failure status
- User, filters, and format
- File size (for exports)

Access audit logs via:
```http
GET /api/v1/reports/audit/
```

## Admin Interface

Manage reports via Django admin:

- **Report Audit Logs**: View generation history (read-only)
- **Report Schedules**: Create and manage scheduled reports

Access at: `/admin/reports/`

## Development

### Adding a New Report

1. Create generator class:
```python
from apps.reports.generators.base import BaseReportGenerator
from apps.reports.registry import register_report

@register_report('my_report')
class MyReportGenerator(BaseReportGenerator):
    report_type = 'my_report'
    report_name = 'My Custom Report'
    
    def get_queryset(self):
        # Return filtered queryset
        pass
    
    def calculate_metrics(self, queryset):
        # Calculate and return metrics
        pass
```

2. Create PDF template (optional):
```html
<!-- apps/reports/templates/reports/my_report.html -->
{% extends "reports/base_report.html" %}
{% block content %}
  <!-- Your report content -->
{% endblock %}
```

3. Register in exporter template maps (if custom template needed)

### Running Tests

```bash
# Run all report tests
python manage.py test apps.reports --settings=config.settings_dev

# Run specific test
python manage.py test apps.reports.tests.test_generators --settings=config.settings_dev
```

## Celery Configuration

For scheduled reports, configure Celery Beat:

```python
# config/celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'execute-scheduled-reports': {
        'task': 'apps.reports.tasks.execute_scheduled_reports',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}
```

## Dependencies

- `weasyprint==60.1` - PDF generation
- `openpyxl==3.1.2` - Excel generation
- `celery==5.3.4` - Background tasks
- `redis==5.0.1` - Caching

## Troubleshooting

### WeasyPrint Installation Issues

On Ubuntu/Debian:
```bash
apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0
pip install weasyprint
```

### Report Generation Fails

Check audit logs:
```http
GET /api/v1/reports/audit/?status=failed
```

### Scheduled Reports Not Running

1. Ensure Celery Beat is running
2. Check Celery logs
3. Verify schedule configuration
4. Check email settings

## Support

For issues or questions:
- Check audit logs for error details
- Review Django logs
- Contact: support@fieldpilot.com
