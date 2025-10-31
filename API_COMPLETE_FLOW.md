# FieldPilot API - Complete User Journey

## 🎯 Overview

This document describes the complete user journey from registration to subscription management.

## 📱 Complete Flow

### Phase 1: User Registration & Verification

```
1. User visits website
2. Clicks "Sign Up"
3. Fills registration form
4. Receives OTP via email
5. Verifies email with OTP
6. Account activated
```

**API Calls:**
```bash
# Step 1: Register
POST /api/v1/auth/register/
{
  "email": "john@acme.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "role": "admin"
}

# Step 2: Verify Email
POST /api/v1/auth/verify-email/
{
  "email": "john@acme.com",
  "otp_code": "123456"
}

# Step 3: Login
POST /api/v1/auth/login/
{
  "email": "john@acme.com",
  "password": "SecurePass123!"
}
# Returns: access_token, refresh_token
```

### Phase 2: Company Onboarding

```
1. User creates company profile
2. Enters company details
3. Gets 14-day free trial
4. Becomes company owner
```

**API Calls:**
```bash
# Step 1: Create Company
POST /api/v1/onboarding/create/
Authorization: Bearer <access_token>
{
  "name": "Acme Corporation",
  "company_email": "contact@acme.com",
  "company_phone": "+1234567890",
  "company_size": "11-50",
  "industry": "Manufacturing",
  "city": "New York",
  "state": "NY",
  "country": "USA"
}
# Returns: tenant_id, trial_ends_at, onboarding_step: 1

# Step 2: Complete Onboarding Step 1
POST /api/v1/onboarding/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 1
}
```

### Phase 3: Subscription Selection

```
1. User views available plans
2. Compares features
3. Selects plan (Starter/Professional/Enterprise)
4. Chooses billing cycle (monthly/yearly)
```

**API Calls:**
```bash
# Step 1: View Plans
GET /api/v1/billing/plans/

# Response:
[
  {
    "id": "uuid",
    "name": "Starter",
    "slug": "starter",
    "price_monthly": 29.00,
    "price_yearly": 290.00,
    "max_users": 5,
    "max_equipment": 50,
    "features": {...}
  },
  {
    "id": "uuid",
    "name": "Professional",
    "slug": "professional",
    "price_monthly": 99.00,
    "price_yearly": 990.00,
    "max_users": 25,
    "max_equipment": 500,
    "features": {...}
  },
  {
    "id": "uuid",
    "name": "Enterprise",
    "slug": "enterprise",
    "price_monthly": 299.00,
    "price_yearly": 2990.00,
    "max_users": null,  # unlimited
    "max_equipment": null,
    "features": {...}
  }
]

# Step 2: Complete Onboarding Step 2
POST /api/v1/onboarding/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 2,
  "data": {
    "selected_plan": "professional",
    "billing_cycle": "monthly"
  }
}
```

### Phase 4: Payment Setup

```
1. User enters payment method
2. Stripe processes payment
3. Subscription activated
4. Trial converted to paid
```

**API Calls:**
```bash
# Step 1: Create Setup Intent (for adding payment method)
POST /api/v1/billing/setup-intent/
Authorization: Bearer <access_token>

# Response:
{
  "client_secret": "seti_xxx_secret_xxx"
}

# Step 2: Frontend uses Stripe.js to collect payment method
# (This happens in the frontend with Stripe Elements)

# Step 3: Create Subscription
POST /api/v1/billing/subscription/create/
Authorization: Bearer <access_token>
{
  "plan_slug": "professional",
  "billing_cycle": "monthly",
  "payment_method_id": "pm_xxx"  # From Stripe.js
}

# Response:
{
  "id": "uuid",
  "plan": {...},
  "status": "active",
  "current_period_start": "2025-10-31T...",
  "current_period_end": "2025-11-30T...",
  "billing_cycle": "monthly",
  "amount": 99.00
}

# Step 4: Complete Onboarding Step 3
POST /api/v1/onboarding/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 3
}
```

### Phase 5: Team Invitation

```
1. Owner invites team members
2. Members receive invitation emails
3. Members join company
4. Roles assigned
```

**API Calls:**
```bash
# Step 1: Invite Team Members
POST /api/v1/onboarding/members/invite/
Authorization: Bearer <access_token>
{
  "email": "jane@acme.com",
  "role": "manager",
  "first_name": "Jane",
  "last_name": "Smith"
}

POST /api/v1/onboarding/members/invite/
Authorization: Bearer <access_token>
{
  "email": "bob@acme.com",
  "role": "employee",
  "first_name": "Bob",
  "last_name": "Johnson"
}

# Step 2: View Team Members
GET /api/v1/onboarding/members/
Authorization: Bearer <access_token>

# Step 3: Complete Onboarding Step 4
POST /api/v1/onboarding/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 4
}
```

### Phase 6: Complete Setup

```
1. User reviews setup
2. Completes onboarding
3. Redirected to dashboard
```

**API Calls:**
```bash
# Complete Final Onboarding Step
POST /api/v1/onboarding/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 5
}

# Response:
{
  "id": "uuid",
  "name": "Acme Corporation",
  "onboarding_completed": true,
  "onboarding_step": 5,
  ...
}
```

## 🔄 Ongoing Operations

### Subscription Management

```bash
# View Current Subscription
GET /api/v1/billing/subscription/
Authorization: Bearer <access_token>

# Upgrade/Downgrade Plan
PUT /api/v1/billing/subscription/update/
Authorization: Bearer <access_token>
{
  "plan_slug": "enterprise",
  "billing_cycle": "yearly"
}

# Cancel Subscription
POST /api/v1/billing/subscription/cancel/
Authorization: Bearer <access_token>
{
  "cancel_immediately": false,
  "reason": "Switching to competitor"
}

# View Billing Overview
GET /api/v1/billing/overview/
Authorization: Bearer <access_token>

# View Invoices
GET /api/v1/billing/invoices/
Authorization: Bearer <access_token>

# View Payments
GET /api/v1/billing/payments/
Authorization: Bearer <access_token>
```

### Company Management

```bash
# View Company Info
GET /api/v1/onboarding/current/
Authorization: Bearer <access_token>

# Update Company Info
PUT /api/v1/onboarding/update/
Authorization: Bearer <access_token>
{
  "company_phone": "+1234567891",
  "website": "https://acme.com",
  "address": "123 Main St"
}
```

### User Profile Management

```bash
# View Profile
GET /api/v1/auth/profile/
Authorization: Bearer <access_token>

# Update Profile
PUT /api/v1/auth/profile/update/
Authorization: Bearer <access_token>
{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "timezone": "America/New_York"
}

# Change Password
POST /api/v1/auth/change-password/
Authorization: Bearer <access_token>
{
  "current_password": "SecurePass123!",
  "new_password": "NewSecurePass456!",
  "new_password_confirm": "NewSecurePass456!"
}
```

## 📊 Onboarding Steps Breakdown

| Step | Name | Description | API Endpoint |
|------|------|-------------|--------------|
| 1 | Company Info | Enter company details | POST /api/v1/onboarding/create/ |
| 2 | Choose Plan | Select subscription plan | GET /api/v1/billing/plans/ |
| 3 | Payment Setup | Add payment method & subscribe | POST /api/v1/billing/subscription/create/ |
| 4 | Invite Team | Invite team members | POST /api/v1/onboarding/members/invite/ |
| 5 | Complete | Finish onboarding | POST /api/v1/onboarding/onboarding/step/ |

## 🎭 User Roles & Permissions

| Role | Permissions |
|------|-------------|
| **Owner** | Full access, billing, delete company |
| **Admin** | Manage users, settings, view billing |
| **Manager** | Manage equipment, facilities, tasks |
| **Employee** | View and update assigned tasks |

## 💳 Subscription Plans

| Plan | Price (Monthly) | Price (Yearly) | Users | Equipment | Features |
|------|----------------|----------------|-------|-----------|----------|
| **Starter** | $29 | $290 (save $58) | 5 | 50 | Basic features |
| **Professional** | $99 | $990 (save $198) | 25 | 500 | Advanced features |
| **Enterprise** | $299 | $2,990 (save $598) | Unlimited | Unlimited | All features + priority support |

## 🔐 Authentication Flow

```
1. User logs in → Receives access_token (15 min) & refresh_token (7 days)
2. Access token expires → Use refresh_token to get new access_token
3. Refresh token expires → User must log in again
```

**Token Refresh:**
```bash
POST /api/token/refresh/
{
  "refresh": "<refresh_token>"
}

# Returns new access_token
```

## 📧 Email Notifications

| Event | Recipient | Purpose |
|-------|-----------|---------|
| Registration | User | OTP for email verification |
| Password Reset | User | OTP for password reset |
| Team Invitation | Invitee | Join company invitation |
| Subscription Created | Owner | Confirmation |
| Payment Success | Owner | Receipt |
| Payment Failed | Owner | Action required |
| Trial Ending | Owner | Upgrade reminder |
| Subscription Cancelled | Owner | Confirmation |

## 🎯 Success Metrics

- **Onboarding Completion Rate**: Track users who complete all 5 steps
- **Time to First Value**: Time from registration to first equipment added
- **Trial Conversion Rate**: Users who convert from trial to paid
- **Churn Rate**: Users who cancel subscription

## 🔗 Frontend Integration

### React Example
```javascript
// 1. Register User
const register = async (userData) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/register/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData)
  });
  return response.json();
};

// 2. Login
const login = async (email, password) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);
  return data;
};

// 3. Create Company
const createCompany = async (companyData) => {
  const token = localStorage.getItem('access_token');
  const response = await fetch('http://localhost:8000/api/v1/onboarding/create/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(companyData)
  });
  return response.json();
};
```

## 🎉 Conclusion

This complete flow ensures a smooth user journey from registration to active subscription, with proper onboarding and team setup.
