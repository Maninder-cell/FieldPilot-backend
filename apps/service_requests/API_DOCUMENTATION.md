# Service Requests API Documentation

**Task 21: Complete API Documentation**

Comprehensive documentation for the Customer Service Request & Issue Management API.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Base URL](#base-url)
4. [Response Format](#response-format)
5. [Error Codes](#error-codes)
6. [Customer Endpoints](#customer-endpoints)
7. [Admin Endpoints](#admin-endpoints)
8. [Customer Portal Endpoints](#customer-portal-endpoints)
9. [Examples](#examples)

---

## Overview

The Service Requests API allows customers to submit service requests and issue reports for their equipment, and enables admins/managers to review, accept/reject, and convert requests into tasks.

### Key Features

- Customer service request submission
- Issue reporting with severity levels
- Admin review and approval workflow
- Request-to-task conversion
- Real-time status tracking
- Comments and communication
- File attachments
- Customer feedback and ratings
- Comprehensive reporting and analytics

---

## Authentication

All endpoints require authentication using JWT tokens.

```http
Authorization: Bearer <your_jwt_token>
```

### Roles

- **Customer**: Can create and manage their own service requests
- **Admin/Manager**: Can view all requests, review, accept/reject, and convert to tasks
- **Technician**: Can view assigned tasks (not covered in this API)

---

## Base URL

```
https://api.fieldpilot.com/api/v1/service-requests/
```

---

## Response Format

### Success Response

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... }
}
```

### Error Response

```json
{
  "success": false,
  "message": "Error message",
  "details": {
    "field_name": ["Error description"]
  }
}
```

### Paginated Response

```json
{
  "count": 100,
  "next": "https://api.fieldpilot.com/api/v1/service-requests/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid data |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Customer Endpoints

### 1. Create Service Request

**POST** `/api/v1/service-requests/`

Create a new service request or issue report.

**Permissions**: Customer only

**Request Body**:
```json
{
  "equipment_id": "uuid",
  "request_type": "service|issue|maintenance|inspection",
  "title": "string",
  "description": "string",
  "priority": "low|medium|high|urgent",
  "issue_type": "breakdown|malfunction|safety|performance|other",
  "severity": "minor|moderate|major|critical"
}
```

**Note**: `issue_type` and `severity` are required when `request_type` is "issue".

**Response**: `201 Created`
```json
{
  "success": true,
  "message": "Service request created successfully",
  "data": {
    "id": "uuid",
    "request_number": "REQ-2025-0001",
    "status": "pending",
    "created_at": "2025-12-11T10:00:00Z",
    ...
  }
}
```

---

### 2. List Service Requests

**GET** `/api/v1/service-requests/`

List all service requests for the authenticated customer.

**Permissions**: Customer only

**Query Parameters**:
- `page` (int): Page number
- `page_size` (int): Items per page (default: 20, max: 100)
- `status` (string): Filter by status
- `priority` (string): Filter by priority
- `request_type` (string): Filter by request type

**Response**: `200 OK`
```json
{
  "count": 50,
  "next": "...",
  "previous": null,
  "results": [ ... ]
}
```

---

### 3. Get Service Request Details

**GET** `/api/v1/service-requests/{request_id}/`

Get detailed information about a specific service request.

**Permissions**: Request owner only

**Response**: `200 OK`

---

### 4. Update Service Request

**PATCH** `/api/v1/service-requests/{request_id}/`

Update service request details (only allowed before review).

**Permissions**: Request owner only

**Request Body**:
```json
{
  "title": "string",
  "description": "string",
  "priority": "low|medium|high|urgent"
}
```

**Response**: `200 OK`

---

### 5. Cancel Service Request

**DELETE** `/api/v1/service-requests/{request_id}/`

Cancel a pending or under review service request.

**Permissions**: Request owner only

**Response**: `200 OK`

---

### 6. Get Request Timeline

**GET** `/api/v1/service-requests/{request_id}/timeline/`

Get complete timeline of all actions taken on the request.

**Permissions**: Request owner or admin

**Response**: `200 OK`
```json
{
  "success": true,
  "data": [
    {
      "action_type": "created",
      "description": "Request created by John Doe",
      "created_at": "2025-12-11T10:00:00Z",
      "user": { ... }
    },
    ...
  ]
}
```

---

### 7. List/Add Comments

**GET/POST** `/api/v1/service-requests/{request_id}/comments/`

List comments or add a new comment.

**Permissions**: Request owner or admin

**POST Request Body**:
```json
{
  "comment_text": "string",
  "is_internal": false
}
```

**Note**: Customers can only create public comments (`is_internal: false`).

---

### 8. Upload Attachment

**POST** `/api/v1/service-requests/{request_id}/attachments/`

Upload a file attachment.

**Permissions**: Request owner or admin

**Request**: Multipart form data
- `file`: File to upload (max 10MB)

**Allowed file types**: JPG, PNG, GIF, PDF, Word documents

**Response**: `201 Created`

---

### 9. Submit Feedback

**POST** `/api/v1/service-requests/{request_id}/feedback/`

Submit feedback and rating for a completed request.

**Permissions**: Request owner only

**Requirements**: Request must be completed

**Request Body**:
```json
{
  "rating": 5,
  "feedback_text": "Excellent service!"
}
```

**Response**: `200 OK`

---

### 10. Respond to Clarification

**POST** `/api/v1/service-requests/{request_id}/clarification/respond/`

Respond to a clarification request from admin.

**Permissions**: Request owner only

**Request Body**:
```json
{
  "message": "Here are the additional details you requested..."
}
```

**Response**: `200 OK`

---

## Admin Endpoints

### 1. List All Service Requests (Admin)

**GET** `/api/v1/service-requests/admin/`

List all service requests across all customers.

**Permissions**: Admin/Manager only

**Query Parameters**:
- `page`, `page_size`: Pagination
- `status`: Filter by status
- `priority`: Filter by priority
- `customer`: Filter by customer ID
- `equipment`: Filter by equipment ID
- `request_type`: Filter by request type

**Response**: `200 OK` (includes internal notes and cost information)

---

### 2. Mark Under Review

**POST** `/api/v1/service-requests/{request_id}/review/`

Mark a request as under review.

**Permissions**: Admin/Manager only

**Response**: `200 OK`

---

### 3. Update Internal Notes

**PATCH** `/api/v1/service-requests/{request_id}/internal-notes/`

Update internal notes (not visible to customer).

**Permissions**: Admin/Manager only

**Request Body**:
```json
{
  "internal_notes": "string"
}
```

**Response**: `200 OK`

---

### 4. Accept Request

**POST** `/api/v1/service-requests/{request_id}/accept/`

Accept a service request.

**Permissions**: Admin/Manager only

**Request Body**:
```json
{
  "response_message": "We will handle this request",
  "estimated_timeline": "2-3 business days",
  "estimated_cost": 500.00
}
```

**Response**: `200 OK`

**Notifications**: Customer receives acceptance notification

---

### 5. Reject Request

**POST** `/api/v1/service-requests/{request_id}/reject/`

Reject a service request.

**Permissions**: Admin/Manager only

**Request Body**:
```json
{
  "rejection_reason": "This service is not covered under your plan"
}
```

**Response**: `200 OK`

**Notifications**: Customer receives rejection notification

---

### 6. Convert to Task

**POST** `/api/v1/service-requests/{request_id}/convert-to-task/`

Convert an accepted request into a task.

**Permissions**: Admin/Manager only

**Requirements**: Request must be in 'accepted' status

**Request Body**:
```json
{
  "priority": "high",
  "scheduled_start": "2025-12-15T09:00:00Z",
  "scheduled_end": "2025-12-15T17:00:00Z",
  "assignee_ids": ["uuid1", "uuid2"]
}
```

**Response**: `200 OK`

**Side Effects**:
- Creates new task
- Links task to request
- Copies attachments to task
- Assigns technicians
- Updates request status to 'in_progress'

---

### 7. Request Clarification

**POST** `/api/v1/service-requests/{request_id}/clarification/`

Request additional information from customer.

**Permissions**: Admin/Manager only

**Request Body**:
```json
{
  "message": "Could you provide more details about the issue?"
}
```

**Response**: `200 OK`

**Notifications**: Customer receives clarification request

---

### 8. Get Reports

**GET** `/api/v1/service-requests/reports/`

Get comprehensive reports and analytics.

**Permissions**: Admin/Manager only

**Query Parameters**:
- `start_date`: Start date for report
- `end_date`: End date for report
- `customer`: Filter by customer ID
- `equipment`: Filter by equipment ID

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "overview": {
      "total_requests": 150,
      "status_breakdown": { ... },
      "avg_response_time_hours": 4.5,
      "avg_resolution_time_hours": 24.8,
      "conversion_rate_percent": 85.5,
      "avg_customer_rating": 4.2
    },
    "time_series": [ ... ],
    "customer_metrics": { ... },
    "equipment_metrics": { ... }
  }
}
```

---

### 9. Get Dashboard Analytics

**GET** `/api/v1/service-requests/reports/analytics/`

Get real-time dashboard analytics.

**Permissions**: Admin/Manager only

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "pending_requests": 15,
    "overdue_requests": [
      {
        "request_number": "REQ-2025-0001",
        "hours_overdue": 36,
        ...
      }
    ],
    "customer_satisfaction": {
      "avg_rating": 4.2,
      "total_ratings": 120,
      "rating_distribution": { ... }
    },
    "technician_performance": [ ... ]
  }
}
```

---

## Customer Portal Endpoints

### 1. Customer Dashboard

**GET** `/api/v1/service-requests/customer/dashboard/`

Get personalized customer dashboard.

**Permissions**: Customer only

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "request_counts": {
      "pending": 2,
      "in_progress": 1,
      "completed": 15
    },
    "recent_activity": [ ... ],
    "equipment_attention": [ ... ],
    "upcoming_services": [ ... ]
  }
}
```

---

### 2. List Customer Equipment

**GET** `/api/v1/service-requests/customer/equipment/`

List all equipment owned by the customer.

**Permissions**: Customer only

**Response**: `200 OK`

---

### 3. Get Equipment Details

**GET** `/api/v1/service-requests/customer/equipment/{equipment_id}/`

Get detailed information about specific equipment.

**Permissions**: Equipment owner only

**Response**: `200 OK`

---

### 4. Get Equipment Service History

**GET** `/api/v1/service-requests/customer/equipment/{equipment_id}/history/`

Get service history for equipment.

**Permissions**: Equipment owner only

**Response**: `200 OK`
```json
{
  "success": true,
  "data": {
    "service_requests": [ ... ],
    "completed_tasks": [ ... ],
    "maintenance_records": [ ... ]
  }
}
```

---

### 5. Get Upcoming Services

**GET** `/api/v1/service-requests/customer/equipment/{equipment_id}/upcoming/`

Get upcoming scheduled services for equipment.

**Permissions**: Equipment owner only

**Response**: `200 OK`

---

## Examples

### Example 1: Customer Creates Service Request

```bash
curl -X POST https://api.fieldpilot.com/api/v1/service-requests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "123e4567-e89b-12d3-a456-426614174000",
    "request_type": "service",
    "title": "Annual Maintenance Required",
    "description": "Equipment needs annual maintenance check",
    "priority": "medium"
  }'
```

---

### Example 2: Customer Reports Critical Issue

```bash
curl -X POST https://api.fieldpilot.com/api/v1/service-requests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "123e4567-e89b-12d3-a456-426614174000",
    "request_type": "issue",
    "title": "Equipment Breakdown",
    "description": "Equipment stopped working completely",
    "priority": "urgent",
    "issue_type": "breakdown",
    "severity": "critical"
  }'
```

---

### Example 3: Admin Accepts Request

```bash
curl -X POST https://api.fieldpilot.com/api/v1/service-requests/{request_id}/accept/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "response_message": "We will handle this request promptly",
    "estimated_timeline": "2-3 business days",
    "estimated_cost": 500.00
  }'
```

---

### Example 4: Admin Converts to Task

```bash
curl -X POST https://api.fieldpilot.com/api/v1/service-requests/{request_id}/convert-to-task/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "priority": "high",
    "scheduled_start": "2025-12-15T09:00:00Z",
    "scheduled_end": "2025-12-15T17:00:00Z",
    "assignee_ids": [
      "tech-uuid-1",
      "tech-uuid-2"
    ]
  }'
```

---

### Example 5: Customer Submits Feedback

```bash
curl -X POST https://api.fieldpilot.com/api/v1/service-requests/{request_id}/feedback/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "feedback_text": "Excellent service! Very professional and timely."
  }'
```

---

### Example 6: Get Reports with Filters

```bash
curl -X GET "https://api.fieldpilot.com/api/v1/service-requests/reports/?start_date=2025-01-01&end_date=2025-12-31&customer=uuid" \
  -H "Authorization: Bearer <admin_token>"
```

---

## Workflow Examples

### Complete Request Lifecycle

1. **Customer creates request** → Status: `pending`
2. **Admin marks under review** → Status: `under_review`
3. **Admin accepts request** → Status: `accepted`
4. **Admin converts to task** → Status: `in_progress`
5. **Technician completes task** → Status: `completed`
6. **Customer submits feedback** → Request closed with rating

### Issue Report Workflow

1. **Customer reports critical issue** → Priority: `urgent`, Severity: `critical`
2. **System sends immediate notification** to admins
3. **Admin reviews and accepts** → Estimated timeline provided
4. **Admin converts to emergency task** → Technician assigned immediately
5. **Technician resolves issue** → Task completed
6. **Request auto-completed** → Customer notified

---

## Rate Limiting

- **Customer endpoints**: 100 requests per minute
- **Admin endpoints**: 200 requests per minute
- **Report endpoints**: 20 requests per minute

---

## Webhooks (Future)

Webhook events will be available for:
- Request created
- Request accepted/rejected
- Task created from request
- Request completed
- Feedback submitted

---

## Support

For API support, contact: api-support@fieldpilot.com

---

**Last Updated**: December 11, 2025  
**API Version**: v1  
**Status**: Production Ready
