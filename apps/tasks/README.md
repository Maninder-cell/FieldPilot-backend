# Task Management System

A comprehensive task management system for the FieldPilot facility management platform.

## Features

### Core Functionality
- ✅ Task creation and assignment to technicians or teams
- ✅ Dual status tracking (admin status + technician work status)
- ✅ Team management for grouping technicians
- ✅ Time tracking (travel, arrival, departure, lunch breaks)
- ✅ Work hours calculation (normal + overtime)
- ✅ Comments and communication
- ✅ File attachments (images, documents)
- ✅ Material tracking (needed vs received)
- ✅ Complete audit history
- ✅ Task scheduling for future execution
- ✅ Notifications for all key events
- ✅ Search, filtering, and pagination
- ✅ Role-based permissions

## Models

### Task
Main task model with auto-generated task numbers (TASK-YYYY-NNNNNN).

**Fields:**
- `equipment` - Equipment this task is for
- `title` - Task title
- `description` - Detailed description
- `status` - Admin status (new, closed, reopened, pending, rejected)
- `priority` - Priority level (low, medium, high, critical)
- `scheduled_start/end` - Scheduling dates
- `materials_needed/received` - Material tracking

### TechnicianTeam
Groups of technicians for team assignments.

**Fields:**
- `name` - Team name (unique)
- `members` - Technician members (ManyToMany)
- `is_active` - Active status

### TaskAssignment
Links tasks to technicians or teams with individual work status.

**Fields:**
- `task` - Task being assigned
- `assignee` - Individual technician (optional)
- `team` - Team assigned (optional)
- `work_status` - Technician work status (open, hold, in_progress, done)

### TimeLog
Tracks technician time on-site with automatic work hours calculation.

**Fields:**
- `travel_started_at` - When travel started
- `arrived_at` - When arrived at site
- `departed_at` - When departed from site
- `lunch_started_at/ended_at` - Lunch break times
- `equipment_status_at_departure` - Equipment status (functional/shutdown)
- `total_work_hours` - Calculated total hours
- `normal_hours` - Normal hours (up to 8)
- `overtime_hours` - Overtime hours (beyond 8)

### TaskComment
Comments for task communication (user or system-generated).

### TaskAttachment
File attachments with type validation and size limits (10MB max).

### TaskHistory
Complete audit trail of all task changes and actions.

### MaterialLog
Tracks materials needed and received for tasks.

## API Endpoints

### Tasks
```
POST   /api/v1/tasks/                    - Create task
GET    /api/v1/tasks/                    - List tasks
GET    /api/v1/tasks/{id}/               - Get task details
PATCH  /api/v1/tasks/{id}/               - Update task
DELETE /api/v1/tasks/{id}/               - Delete task
POST   /api/v1/tasks/{id}/assign/        - Assign task
PATCH  /api/v1/tasks/{id}/status/        - Update admin status
PATCH  /api/v1/tasks/{id}/work-status/   - Update work status
GET    /api/v1/tasks/{id}/history/       - Get task history
```

### Time Tracking
```
POST   /api/v1/tasks/{id}/travel/        - Log travel started
POST   /api/v1/tasks/{id}/arrive/        - Log arrival
POST   /api/v1/tasks/{id}/depart/        - Log departure
POST   /api/v1/tasks/{id}/lunch-start/   - Log lunch start
POST   /api/v1/tasks/{id}/lunch-end/     - Log lunch end
GET    /api/v1/tasks/{id}/time-logs/     - Get time logs
```

### Comments
```
POST   /api/v1/tasks/{id}/comments/      - Add comment
GET    /api/v1/tasks/{id}/comments/      - List comments
PATCH  /api/v1/comments/{id}/            - Update comment
DELETE /api/v1/comments/{id}/            - Delete comment
```

### Attachments
```
POST   /api/v1/tasks/{id}/attachments/   - Upload file
GET    /api/v1/tasks/{id}/attachments/   - List attachments
DELETE /api/v1/attachments/{id}/         - Delete attachment
GET    /api/v1/attachments/{id}/download/ - Download file
```

### Materials
```
POST   /api/v1/tasks/{id}/materials/needed/   - Log materials needed
POST   /api/v1/tasks/{id}/materials/received/ - Log materials received
GET    /api/v1/tasks/{id}/materials/          - Get material logs
```

### Teams
```
POST   /api/v1/teams/                    - Create team
GET    /api/v1/teams/                    - List teams
GET    /api/v1/teams/{id}/               - Get team details
PATCH  /api/v1/teams/{id}/               - Update team
DELETE /api/v1/teams/{id}/               - Delete team
POST   /api/v1/teams/{id}/members/       - Add members
DELETE /api/v1/teams/{id}/members/{uid}/ - Remove member
```

### Reports
```
GET    /api/v1/reports/work-hours/       - Work hours report
```

## Business Logic

### SiteConflictValidator
Prevents technicians from being at multiple sites simultaneously.

```python
from apps.tasks.utils import SiteConflictValidator

can_travel, message = SiteConflictValidator.can_travel(technician)
```

### WorkHoursCalculator
Calculates work hours, normal hours, and overtime.

```python
from apps.tasks.utils import WorkHoursCalculator

total, normal, overtime = WorkHoursCalculator.calculate(time_log)
```

### TaskStatusValidator
Validates status transitions and prerequisites.

```python
from apps.tasks.utils import TaskStatusValidator

can_close, message = TaskStatusValidator.can_close_task(task)
```

## Permissions

### Admin/Manager
- Create tasks
- Update task status and priority
- Assign tasks to technicians/teams
- Create and manage teams
- View all tasks
- Delete tasks

### Technician
- View assigned tasks
- Update work status
- Log time tracking (travel, arrival, departure, lunch)
- Add comments
- Upload attachments
- Log materials

## Notifications

The system sends notifications for:
- Task assignment
- Status changes
- New comments
- Scheduled task activation
- Critical priority tasks (immediate)

## Management Commands

### Activate Scheduled Tasks
```bash
python manage.py activate_scheduled_tasks
```

Activates tasks that have reached their scheduled start date.

## Usage Examples

### Create a Task
```python
POST /api/v1/tasks/
{
    "equipment_id": "uuid",
    "title": "Fix HVAC System",
    "description": "HVAC system not cooling properly",
    "priority": "high",
    "assignee_ids": ["tech-uuid-1", "tech-uuid-2"],
    "materials_needed": [
        {"name": "Refrigerant", "quantity": 2, "unit": "kg"}
    ]
}
```

### Log Time Tracking
```python
# Start travel
POST /api/v1/tasks/{id}/travel/

# Arrive at site
POST /api/v1/tasks/{id}/arrive/

# Start lunch
POST /api/v1/tasks/{id}/lunch-start/

# End lunch
POST /api/v1/tasks/{id}/lunch-end/

# Depart from site
POST /api/v1/tasks/{id}/depart/
{
    "equipment_status": "functional"
}
```

### Get Work Hours Report
```python
GET /api/v1/reports/work-hours/?technician=uuid&start_date=2025-01-01&end_date=2025-01-31
```

## Testing

Run tests:
```bash
python manage.py test apps.tasks
```

## Admin Interface

All models are registered in Django admin for easy management:
- Tasks
- Teams
- Assignments
- Time Logs
- Comments
- Attachments
- History
- Materials

## Database Indexes

Optimized indexes for:
- Task number lookups
- Status and priority filtering
- Equipment-based queries
- Time-based queries
- Technician-based queries

## Error Handling

All endpoints return standardized error responses:
```json
{
    "success": false,
    "error": {
        "code": "ERROR",
        "message": "Error message",
        "details": {}
    }
}
```

## Future Enhancements

- Real-time updates via WebSockets
- Mobile app optimization
- Advanced scheduling (recurring tasks)
- Comprehensive reporting dashboard
- AI-powered task prioritization
- Geofencing for automatic arrival/departure
- Voice notes support
- Offline mode for mobile

## License

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
