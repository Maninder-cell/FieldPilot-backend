# FieldRino API - Complete User Journey

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
POST /api/v1/onboarding/step/
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
POST /api/v1/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 2,
  "data": {
    "selected_plan": "professional",
    "billing_cycle": "monthly"
  }
}
```

### Phase 4: Payment Setup & Subscription Creation

```
1. User selects plan and billing cycle
2. Frontend creates setup intent (saves payment method)
3. User enters credit card details via Stripe.js
4. Frontend creates subscription with payment method
5. Subscription created in Stripe with 'trialing' status (if trial active)
6. Stripe automatically handles billing after trial ends
```

**⚠️ IMPORTANT: Stripe-Managed Billing**
- **During Trial**: Card is saved but NOT charged by Stripe
- **After Trial**: Stripe automatically charges the card when trial ends
- **Automatic Renewals**: Stripe handles all recurring billing automatically
- **No Manual Processing**: No Celery tasks needed - Stripe does everything
- **Webhooks**: Stripe notifies your app of all billing events

**API Calls:**

#### Step 1: Create Setup Intent (Save Payment Method)
```bash
POST /api/v1/billing/setup-intent/
Authorization: Bearer <access_token>

# Response:
{
  "success": true,
  "data": {
    "client_secret": "seti_1234567890_secret_abcdefghijk",
    "customer_id": "cus_1234567890"
  },
  "message": "Setup intent created successfully"
}
```

#### Step 2: Frontend Payment Collection (Stripe.js)
```javascript
// Load Stripe.js in your frontend
const stripe = Stripe('pk_test_51MbL2qSIYrrF4K92A6XOcxrcly3r6QqoZI8gCGyFSW9gaCiOPBg0Z1IKNQFRKZw8HvaFxjFBt3FBpLmOIuXAczHh00yT7c7TBC');

// Create card element
const elements = stripe.elements();
const cardElement = elements.create('card', {
  style: {
    base: {
      fontSize: '16px',
      color: '#424770',
      '::placeholder': {
        color: '#aab7c4',
      },
    },
  },
});
cardElement.mount('#card-element');

// Confirm setup intent with card
const {error, setupIntent} = await stripe.confirmCardSetup(
  client_secret, // From step 1
  {
    payment_method: {
      card: cardElement,
      billing_details: {
        name: 'John Doe',
        email: 'john@acme.com'
      }
    }
  }
);

if (error) {
  // Show error to customer
  console.error('Payment setup failed:', error.message);
} else {
  // Payment method saved successfully
  const payment_method_id = setupIntent.payment_method;
  console.log('Payment method saved:', payment_method_id);
  
  // Now create subscription with this payment method
  createSubscription(payment_method_id);
}
```

#### Step 3: Create Subscription with Payment Method
```bash
POST /api/v1/billing/subscription/create/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "plan_slug": "professional",
  "billing_cycle": "monthly",
  "payment_method_id": "pm_1234567890abcdef"  # From Stripe.js
}

# Response (During Trial):
{
  "success": true,
  "data": {
    "id": "uuid",
    "plan": {
      "name": "Professional",
      "slug": "professional",
      "price_monthly": "79.00",
      "price_yearly": "790.00"
    },
    "status": "trialing",  # ← Trial status
    "billing_cycle": "monthly",
    "trial_start": "2025-11-25T10:00:00Z",
    "trial_end": "2025-12-09T10:00:00Z",  # ← 14 days from now
    "current_period_start": "2025-12-09T10:00:00Z",  # ← Billing starts after trial
    "current_period_end": "2026-01-09T10:00:00Z",
    "is_trial": true,
    "stripe_customer_id": "cus_1234567890",
    "days_until_renewal": 14,
    "current_users_count": 1,
    "current_equipment_count": 0
  },
  "message": "Subscription created successfully"
}

# Note: Card is saved but NO CHARGE is made during trial.
# First payment of $79.00 will be automatically charged by Stripe on 2025-12-09 (trial_end date).
# Stripe handles all recurring billing automatically - no manual processing needed.
```

#### Step 4: Complete Onboarding
```bash
POST /api/v1/onboarding/step/
Authorization: Bearer <access_token>
{
  "step": 3
}
```

**Frontend Integration Notes:**
- **Stripe.js Library**: Include `<script src="https://js.stripe.com/v3/"></script>`
- **PCI Compliance**: Card details never touch your server
- **Test Cards**: Use `4242 4242 4242 4242` for testing
- **Error Handling**: Handle card declined, expired, etc.
- **Loading States**: Show spinner during payment setup
- **Success Flow**: Redirect to dashboard after subscription creation

**Security & Best Practices:**
- ✅ Use HTTPS in production
- ✅ Validate on both frontend and backend
- ✅ Handle all Stripe error types
- ✅ Show clear success/error messages
- ✅ Never log sensitive payment data

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
POST /api/v1/onboarding/step/
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
POST /api/v1/onboarding/step/
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
# View Current Subscription (fetches live data from Stripe)
GET /api/v1/billing/subscription/
Authorization: Bearer <access_token>

# Response (data comes from Stripe):
{
  "success": true,
  "data": {
    "id": "uuid",
    "plan": {...},
    "status": "active",  # From Stripe
    "billing_cycle": "monthly",  # From Stripe
    "current_period_start": "2025-10-31T...",  # From Stripe
    "current_period_end": "2025-11-30T...",  # From Stripe
    "cancel_at_period_end": false,  # From Stripe
    "trial_start": null,  # From Stripe
    "trial_end": null,  # From Stripe
    "current_users_count": 3,  # Local usage tracking
    "current_equipment_count": 15,  # Local usage tracking
    "days_until_renewal": 30
  }
}

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

# View Invoices (fetches from Stripe)
GET /api/v1/billing/invoices/?limit=10&starting_after=in_xxx
Authorization: Bearer <access_token>

# Response (Stripe invoices):
{
  "success": true,
  "data": [
    {
      "id": "in_1234567890",
      "number": "INV-001",
      "amount_due": 7900,  # In cents ($79.00)
      "amount_paid": 7900,
      "currency": "usd",
      "status": "paid",
      "invoice_pdf": "https://stripe.com/invoices/...",
      "created": 1234567890,  # Unix timestamp
      "period_start": 1234567890,
      "period_end": 1234567890
    }
  ]
}

# View Payments (fetches from Stripe)
GET /api/v1/billing/payments/?limit=10&starting_after=ch_xxx
Authorization: Bearer <access_token>

# Response (Stripe charges):
{
  "success": true,
  "data": [
    {
      "id": "ch_1234567890",
      "amount": 7900,  # In cents ($79.00)
      "currency": "usd",
      "status": "succeeded",
      "payment_method_details": {
        "type": "card",
        "brand": "visa",
        "last4": "4242"
      },
      "receipt_url": "https://stripe.com/receipts/...",
      "created": 1234567890
    }
  ]
}

# Manage Payment Methods
GET /api/v1/billing/payment-methods/
Authorization: Bearer <access_token>

POST /api/v1/billing/payment-methods/set-default/
Authorization: Bearer <access_token>
{
  "payment_method_id": "pm_1234567890"
}

DELETE /api/v1/billing/payment-methods/pm_1234567890/
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

| Step | Name | Description | API Endpoints | Frontend Requirements |
|------|------|-------------|---------------|----------------------|
| 1 | Company Info | Enter company details | POST /api/v1/onboarding/create/ | Company form |
| 2 | Choose Plan | Select subscription plan | GET /api/v1/billing/plans/ | Plan selection UI |
| 3 | Payment Setup | Save card & create subscription | POST /api/v1/billing/setup-intent/<br>POST /api/v1/billing/subscription/create/ | Stripe.js integration<br>Card element |
| 4 | Invite Team | Invite team members | POST /api/v1/onboarding/members/invite/ | Email invitation form |
| 5 | Complete | Finish onboarding | POST /api/v1/onboarding/step/ | Success page |

## 🎭 User Roles & Permissions

| Role | Permissions |
|------|-------------|
| **Owner** | Full access, billing, delete company |
| **Admin** | Manage users, settings, view billing |
| **Manager** | Manage equipment, facilities, tasks |
| **Employee** | View and update assigned tasks |

## 💳 Subscription Plans

| Plan | Price (Monthly) | Price (Yearly) | Users | Equipment | Storage | Features |
|------|----------------|----------------|-------|-----------|---------|----------|
| **Starter** | $29 | $290 (save $58) | 5 | 50 | 5GB | Basic features |
| **Professional** | $79 | $790 (save $158) | 25 | 250 | 25GB | Advanced features + API access |
| **Enterprise** | $199 | $1,990 (save $398) | Unlimited | Unlimited | Unlimited | All features + priority support |

**Free Trial & Payment Timing:**
- **14-day free trial** for all new tenants
- Card is saved but **NOT charged during trial**
- Stripe automatically charges first payment after trial ends (day 14)
- Stripe handles all recurring payments every 30 days (monthly) or 365 days (yearly)

**Stripe Automatic Billing:**
- Stripe automatically processes all subscription renewals
- Stripe's Smart Retries handle failed payments (up to 4 attempts over 3 weeks)
- Stripe sends email notifications for payment success/failure
- Webhooks keep your app synchronized with Stripe billing events

**Plans are automatically seeded when you run `./start.sh` or `python manage.py seed_plans`**

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

### Complete React/JavaScript Example

#### 1. HTML Setup
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://js.stripe.com/v3/"></script>
</head>
<body>
  <div id="card-element">
    <!-- Stripe Elements will create form elements here -->
  </div>
  <button id="submit-payment">Subscribe</button>
</body>
</html>
```

#### 2. JavaScript Implementation
```javascript
// Initialize Stripe
const stripe = Stripe('pk_test_51MbL2qSIYrrF4K92A6XOcxrcly3r6QqoZI8gCGyFSW9gaCiOPBg0Z1IKNQFRKZw8HvaFxjFBt3FBpLmOIuXAczHh00yT7c7TBC');
const elements = stripe.elements();

// Create card element
const cardElement = elements.create('card', {
  style: {
    base: {
      fontSize: '16px',
      color: '#424770',
      '::placeholder': { color: '#aab7c4' }
    }
  }
});
cardElement.mount('#card-element');

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
  if (data.success) {
    localStorage.setItem('access_token', data.data.tokens.access);
    localStorage.setItem('refresh_token', data.data.tokens.refresh);
  }
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

// 4. Complete Payment Setup & Subscription
const createSubscriptionWithPayment = async (planSlug, billingCycle) => {
  const token = localStorage.getItem('access_token');
  
  try {
    // Step 1: Create setup intent
    console.log('Creating setup intent...');
    const setupResponse = await fetch('http://localhost:8000/api/v1/billing/setup-intent/', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const setupData = await setupResponse.json();
    if (!setupData.success) {
      throw new Error(setupData.error.message);
    }
    
    const clientSecret = setupData.data.client_secret;
    console.log('Setup intent created:', clientSecret);
    
    // Step 2: Confirm card setup with Stripe
    console.log('Confirming card setup...');
    const {error, setupIntent} = await stripe.confirmCardSetup(clientSecret, {
      payment_method: {
        card: cardElement,
        billing_details: {
          name: 'John Doe',
          email: 'john@acme.com'
        }
      }
    });
    
    if (error) {
      console.error('Card setup failed:', error.message);
      throw new Error(error.message);
    }
    
    console.log('Card saved successfully:', setupIntent.payment_method);
    
    // Step 3: Create subscription with payment method
    console.log('Creating subscription...');
    const subscriptionResponse = await fetch('http://localhost:8000/api/v1/billing/subscription/create/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        plan_slug: planSlug,
        billing_cycle: billingCycle,
        payment_method_id: setupIntent.payment_method
      })
    });
    
    const subscriptionData = await subscriptionResponse.json();
    if (!subscriptionData.success) {
      throw new Error(subscriptionData.error.message);
    }
    
    console.log('Subscription created successfully:', subscriptionData.data);
    return subscriptionData;
    
  } catch (error) {
    console.error('Payment setup failed:', error.message);
    throw error;
  }
};

// 5. Event Handler
document.getElementById('submit-payment').addEventListener('click', async () => {
  const button = document.getElementById('submit-payment');
  button.disabled = true;
  button.textContent = 'Processing...';
  
  try {
    await createSubscriptionWithPayment('professional', 'monthly');
    alert('Subscription created successfully!');
    // Redirect to dashboard
    window.location.href = '/dashboard';
  } catch (error) {
    alert('Payment failed: ' + error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Subscribe';
  }
});
```

#### 3. React Component Example
```jsx
import React, { useState, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  CardElement,
  useStripe,
  useElements
} from '@stripe/react-stripe-js';

const stripePromise = loadStripe('pk_test_51MbL2qSIYrrF4K92A6XOcxrcly3r6QqoZI8gCGyFSW9gaCiOPBg0Z1IKNQFRKZw8HvaFxjFBt3FBpLmOIuXAczHh00yT7c7TBC');

const CheckoutForm = ({ planSlug, billingCycle }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    if (!stripe || !elements) return;

    try {
      // Create setup intent
      const token = localStorage.getItem('access_token');
      const setupResponse = await fetch('/api/v1/billing/setup-intent/', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const setupData = await setupResponse.json();
      const clientSecret = setupData.data.client_secret;

      // Confirm card setup
      const {error, setupIntent} = await stripe.confirmCardSetup(clientSecret, {
        payment_method: {
          card: elements.getElement(CardElement),
          billing_details: { name: 'John Doe' }
        }
      });

      if (error) {
        setError(error.message);
        return;
      }

      // Create subscription
      const subscriptionResponse = await fetch('/api/v1/billing/subscription/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          plan_slug: planSlug,
          billing_cycle: billingCycle,
          payment_method_id: setupIntent.payment_method
        })
      });

      const subscriptionData = await subscriptionResponse.json();
      if (subscriptionData.success) {
        // Success! Redirect to dashboard
        window.location.href = '/dashboard';
      } else {
        setError(subscriptionData.error.message);
      }

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <CardElement
        options={{
          style: {
            base: {
              fontSize: '16px',
              color: '#424770',
              '::placeholder': { color: '#aab7c4' }
            }
          }
        }}
      />
      {error && <div style={{color: 'red'}}>{error}</div>}
      <button type="submit" disabled={!stripe || loading}>
        {loading ? 'Processing...' : 'Subscribe'}
      </button>
    </form>
  );
};

const PaymentPage = () => (
  <Elements stripe={stripePromise}>
    <CheckoutForm planSlug="professional" billingCycle="monthly" />
  </Elements>
);

export default PaymentPage;
```

## 🚀 Quick Start Checklist

### Backend Setup
- [ ] Clone repository
- [ ] Create `.env` file from `.env.example`
- [ ] Add Stripe keys: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- [ ] Configure webhook endpoint in Stripe Dashboard: `https://yourdomain.com/api/v1/billing/webhooks/stripe/`
- [ ] Run `./start.sh` (automatically runs migrations, seeds plans, starts server)
- [ ] Access Swagger docs at `http://localhost:8000/api/docs/`
- [ ] Start Celery (optional, for usage tracking): `celery -A config worker -l info`

### Frontend Setup
- [ ] Include Stripe.js: `<script src="https://js.stripe.com/v3/"></script>`
- [ ] Initialize Stripe with publishable key
- [ ] Create card element for payment collection
- [ ] Implement setup intent → card collection → subscription flow

### Testing the Complete Flow
1. [ ] Register user via `/api/v1/auth/register/`
2. [ ] Verify email with OTP via `/api/v1/auth/verify-email/`
3. [ ] Login via `/api/v1/auth/login/`
4. [ ] Create company via `/api/v1/onboarding/create/`
5. [ ] View plans via `/api/v1/billing/plans/`
6. [ ] Create setup intent via `/api/v1/billing/setup-intent/`
7. [ ] Use Stripe.js to collect card: `4242 4242 4242 4242`
8. [ ] Create subscription with payment method via `/api/v1/billing/subscription/create/`
9. [ ] Complete onboarding via `/api/v1/onboarding/step/`

### Stripe Test Cards
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires 3D Secure**: `4000 0025 0000 3155`
- **Insufficient Funds**: `4000 0000 0000 9995`
- Use any future expiry date and any 3-digit CVC

### Stripe Webhook Setup (Required for Production)
- [ ] Go to Stripe Dashboard > Developers > Webhooks
- [ ] Add endpoint: `https://yourdomain.com/api/v1/billing/webhooks/stripe/`
- [ ] Select events: `customer.subscription.*`, `invoice.payment_*`
- [ ] Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET` in `.env`
- [ ] Test webhook delivery in Stripe Dashboard

### Background Tasks (Optional, for usage tracking)
- [ ] Start Celery worker: `celery -A config worker -l info`
- [ ] Start Celery beat: `celery -A config beat -l info`
- [ ] Usage counts update daily at midnight
- [ ] Stripe sync runs every 6 hours (backup to webhooks)

## 🐛 Troubleshooting

### Backend Issues

#### "No tenant found" Error
- Make sure you've created a company via `/api/v1/onboarding/create/` first
- For SQLite development, the system uses the first tenant automatically

#### "Stripe not configured" Error
- Add `STRIPE_SECRET_KEY` to your `.env` file
- Get test keys from https://dashboard.stripe.com/test/apikeys
- Install Stripe library: `pip install stripe==5.5.0`

#### "'NoneType' object has no attribute 'Secret'" Error
- Stripe library version issue
- Fix: `pip uninstall stripe -y && pip install stripe==5.5.0`
- Restart Django server

#### Token Expired
- Use `/api/v1/auth/token/refresh/` with your refresh token
- Access tokens expire after 15 minutes

### Frontend Issues

#### Stripe.js Not Loading
- Include script: `<script src="https://js.stripe.com/v3/"></script>`
- Check browser console for errors
- Ensure HTTPS in production

#### Card Element Not Mounting
- Ensure DOM element exists before mounting
- Check element ID matches: `cardElement.mount('#card-element')`

#### "Your card was declined"
- Use test cards: `4242 4242 4242 4242`
- Check card details (expiry, CVC)
- Try different test card numbers

#### Setup Intent Fails
- Check network requests in browser dev tools
- Verify authentication token is valid
- Ensure Stripe keys are configured correctly

### Payment Issues

#### Subscription Created But No Payment Method
- Check if setup intent completed successfully
- Verify payment_method_id is passed to subscription creation
- Check Stripe dashboard for customer and payment methods

#### Webhooks Not Working
- Check webhook endpoint is publicly accessible
- Verify `STRIPE_WEBHOOK_SECRET` is correct
- Check Stripe Dashboard > Webhooks for delivery status
- Review webhook event logs in Stripe Dashboard
- Check application logs: `docker-compose logs -f web`

#### Subscription Not Renewing
- Stripe handles renewals automatically - no action needed
- Check Stripe Dashboard > Subscriptions for status
- Verify webhook events are being delivered
- Check customer has valid payment method

## 🔄 Stripe Automatic Billing & Webhooks

### How Stripe Manages Recurring Payments

Once a subscription is created with a payment method, **Stripe automatically handles everything**:

#### Stripe's Automatic Process
```
1. Trial ends → Stripe automatically charges the card
2. Subscription renews → Stripe charges on renewal date
3. Payment succeeds → Stripe sends webhook to your app
4. Payment fails → Stripe's Smart Retries handle it automatically
5. All events → Webhooks keep your app synchronized
```

#### No Manual Processing Needed
- ❌ **No Celery tasks** for billing (only for usage tracking)
- ❌ **No manual charging** - Stripe does it automatically
- ❌ **No invoice generation** - Stripe creates invoices
- ✅ **Webhooks** keep your app in sync
- ✅ **Stripe Dashboard** for monitoring and management

#### Stripe's Smart Retry Logic
Stripe automatically retries failed payments:
- **Attempt 1**: Immediate (when payment fails)
- **Attempt 2**: 3 days later
- **Attempt 3**: 5 days after attempt 2
- **Attempt 4**: 7 days after attempt 3
- **Total**: Up to 4 attempts over ~3 weeks
- **Emails**: Stripe sends notifications to customers

#### Webhook Events
Your app receives real-time notifications from Stripe:

```bash
# Webhook endpoint (configured in Stripe Dashboard)
POST /api/v1/billing/webhooks/stripe/

# Events handled:
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_succeeded
- invoice.payment_failed
```

### Subscription Lifecycle (Stripe-Managed)

```
┌─────────────────────────────────────────────────────────────┐
│              STRIPE-MANAGED SUBSCRIPTION STATES              │
└─────────────────────────────────────────────────────────────┘

trialing ──trial ends──> active (Stripe charges automatically)
  │
active ──renewal date──> active (Stripe charges automatically)
  │
  │ payment fails
  ↓
past_due ──Stripe retries──> active (if retry succeeds)
  │
  │ all retries fail
  ↓
unpaid ──after grace period──> canceled

# Your app receives webhooks for all state changes
```

### Background Tasks (Celery)

Only 2 tasks needed (not for billing):

```bash
# Start Celery worker
celery -A config worker -l info

# Start Celery beat (scheduler)
celery -A config beat -l info
```

**Tasks:**
1. **update_all_usage_counts** (daily at midnight)
   - Updates local usage tracking (users, equipment, storage)
   - Used for plan limit enforcement

2. **sync_subscriptions_from_stripe** (every 6 hours)
   - Backup sync in case webhooks are missed
   - Ensures local data matches Stripe

### Monitoring & Analytics

#### Via Your App
```bash
# Check billing health
python manage.py check_billing_health

# Get metrics
python manage.py check_billing_health --json

# Output:
{
  "subscription_metrics": {
    "total_subscriptions": 150,
    "active_subscriptions": 142,
    "trialing_subscriptions": 8,
    "past_due_subscriptions": 2,
    "churn_rate": 5.3
  },
  "payment_health": {
    "payment_failure_rate": 1.4,
    "payment_health_status": "healthy"
  },
  "revenue_metrics": {
    "monthly_recurring_revenue": 11218.00,
    "annual_recurring_revenue": 134616.00
  }
}
```

#### Via Stripe Dashboard
- **Revenue**: https://dashboard.stripe.com
- **Subscriptions**: https://dashboard.stripe.com/subscriptions
- **Customers**: https://dashboard.stripe.com/customers
- **Invoices**: https://dashboard.stripe.com/invoices
- **Failed Payments**: https://dashboard.stripe.com/payments?status=failed
- **Webhooks**: https://dashboard.stripe.com/webhooks

## 🎉 Conclusion

This complete flow ensures a smooth user journey from registration to active subscription with automatic renewals:

### ✅ What You Have
- **Complete user onboarding** (registration → company → subscription)
- **Stripe-managed billing** (Stripe handles ALL payment processing)
- **Automatic renewals** (Stripe charges customers automatically)
- **Smart payment retries** (Stripe's built-in retry logic)
- **Real-time webhooks** (instant synchronization with Stripe)
- **Usage tracking** (local monitoring of plan limits)
- **Comprehensive API** (30+ endpoints for all operations)
- **No manual billing** (Stripe does everything automatically)

### 🚀 Production Ready
- **PCI Compliant** (Stripe handles all card data)
- **Fully Automated** (No manual billing tasks needed)
- **Reliable** (Stripe's 99.99% uptime SLA)
- **Scalable** (Stripe handles millions of transactions)
- **Flexible** (Easy plan changes with automatic proration)
- **Monitored** (Stripe Dashboard + custom health checks)
- **Secure** (Webhook signature verification)

### 📖 Documentation
- **Swagger UI**: `http://localhost:8000/api/docs/` - Interactive API testing
- **ReDoc**: `http://localhost:8000/api/redoc/` - Clean documentation
- **Complete guides**: All markdown files in the repository

Your SaaS billing system is now **production-ready** with enterprise-grade features! 🎯
