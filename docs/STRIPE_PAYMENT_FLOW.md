# Stripe Payment Flow - Complete Guide

## Overview

FieldRino uses a **hybrid approach**:
- **Backend manages subscriptions** (Django)
- **Stripe processes payments** (Optional)

## How Recurring Payments Work

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SUBSCRIPTION LIFECYCLE                    │
└─────────────────────────────────────────────────────────────┘

1. SETUP (One-time)
   ┌──────────────┐
   │ Setup Intent │ → Collect card → Save to Stripe Customer
   └──────────────┘

2. SUBSCRIPTION CREATION
   ┌──────────────┐
   │ Create Sub   │ → Store in Django DB → Link to Stripe Customer
   └──────────────┘

3. RECURRING CHARGES (Automated)
   ┌──────────────┐
   │ Celery Task  │ → Check renewals → Charge saved card → Update DB
   └──────────────┘
```

## Step-by-Step Flow

### Phase 1: Initial Setup (One-time per customer)

**Purpose**: Collect and save payment method for future charges

```bash
# 1. Create Setup Intent
POST /api/v1/billing/setup-intent/
Authorization: Bearer <token>

Response:
{
  "client_secret": "seti_xxx_secret_xxx",
  "customer_id": "cus_xxx"
}
```

**Frontend (React/Vue/etc):**
```javascript
// Load Stripe.js
const stripe = Stripe('pk_test_xxx');

// Create card element
const cardElement = elements.create('card');
cardElement.mount('#card-element');

// Confirm setup intent
const {error, setupIntent} = await stripe.confirmCardSetup(
  client_secret,
  {
    payment_method: {
      card: cardElement,
      billing_details: {
        name: 'John Doe',
        email: 'john@example.com'
      }
    }
  }
);

if (error) {
  console.error(error);
} else {
  // Card saved! setupIntent.payment_method contains the ID
  const payment_method_id = setupIntent.payment_method;
  
  // Now create subscription with this payment method
  createSubscription(payment_method_id);
}
```

### Phase 2: Create Subscription

```bash
# 2. Create Subscription (with or without payment method)
POST /api/v1/billing/subscription/create/
Authorization: Bearer <token>
Content-Type: application/json

{
  "plan_slug": "professional",
  "billing_cycle": "monthly",
  "payment_method_id": "pm_xxx"  # Optional - from setup intent
}

Response (During Trial):
{
  "success": true,
  "data": {
    "id": "uuid",
    "plan": {...},
    "status": "trialing",  # ← Trial status
    "trial_start": "2025-11-25T10:00:00Z",
    "trial_end": "2025-12-09T10:00:00Z",  # ← 14 days
    "current_period_start": "2025-12-09T10:00:00Z",  # ← Billing starts after trial
    "current_period_end": "2026-01-09T10:00:00Z",
    "billing_cycle": "monthly",
    "is_trial": true
  }
}
```

**What happens:**
- Subscription created in Django database
- If payment_method_id provided, linked to Stripe customer
- **During trial**: Status set to "trialing", NO CHARGE made
- **After trial**: Status set to "active", charged immediately
- Billing period calculated from trial end date (if trial active)
- First payment charged automatically when trial ends (day 14)

### Phase 3: Recurring Charges (Automated)

**Celery Beat Schedule** (runs automatically):

```python
# Daily at 2:00 AM - Process renewals and trial conversions
process_subscription_renewals()
  ↓
  1. Find subscriptions where trial ends today
  2. Charge first payment after trial
  3. Convert status from 'trialing' to 'active'
  4. Find subscriptions ending today (renewals)
  5. Calculate renewal amount
  6. Charge Stripe customer (saved card)
  7. Create invoice and payment record
  8. Extend subscription period
```

**How Charging Works:**

```python
# Backend automatically charges the saved card
stripe.PaymentIntent.create(
    amount=7900,  # $79.00 in cents
    currency='usd',
    customer='cus_xxx',  # Stripe customer ID
    off_session=True,  # Customer not present
    confirm=True  # Charge immediately
)
```

## Payment States

### Subscription Status Flow

```
┌──────────┐
│ trialing │ ──trial ends + payment success──> │ active  │
└──────────┘                                    └─────────┘
     │                                               │
     │ trial ends + payment fails                    │ renewal success
     ↓                                               ↓
┌──────────┐                                    ┌─────────┐
│ past_due │ ──retry success──────────────────> │ active  │
└──────────┘                                    └─────────┘
     │                                               │
     │ 3 failed attempts                             │ payment fails
     ↓                                               ↓
┌──────────┐                                    ┌──────────┐
│ canceled │ <────────────────────────────────  │ past_due │
└──────────┘                                    └──────────┘
```

### Payment Retry Logic

1. **First failure**: Status → `past_due`, retry next day
2. **Second failure**: Retry again next day
3. **Third failure**: Cancel subscription

## Celery Tasks Schedule

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_subscription_renewals` | Daily 2:00 AM | Charge renewals |
| `retry_failed_payments` | Daily 3:00 AM | Retry past_due |
| `send_renewal_reminders` | Daily 9:00 AM | Email reminders |
| `update_usage_counts` | Daily midnight | Update metrics |

## Running Celery

### Development

```bash
# Terminal 1: Start Celery worker
celery -A config worker -l info

# Terminal 2: Start Celery beat (scheduler)
celery -A config beat -l info

# Terminal 3: Django server
python manage.py runserver
```

### Production (with Docker)

```yaml
# docker-compose.yml
services:
  celery-worker:
    build: .
    command: celery -A config worker -l info
    depends_on:
      - redis
      - postgres
  
  celery-beat:
    build: .
    command: celery -A config beat -l info
    depends_on:
      - redis
      - postgres
```

## Testing Payments

### Test Cards (Stripe Test Mode)

| Card Number | Scenario |
|-------------|----------|
| 4242 4242 4242 4242 | Success |
| 4000 0000 0000 0002 | Decline |
| 4000 0025 0000 3155 | Requires authentication |
| 4000 0000 0000 9995 | Insufficient funds |

### Manual Testing

```bash
# 1. Create subscription
curl -X POST http://localhost:8000/api/v1/billing/subscription/create/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_slug": "professional", "billing_cycle": "monthly"}'

# 2. Manually trigger renewal (for testing)
python manage.py shell
>>> from apps.billing.tasks import process_subscription_renewals
>>> process_subscription_renewals()
```

## Webhooks (Optional)

For real-time payment updates, configure Stripe webhooks:

```bash
# Stripe CLI for local testing
stripe listen --forward-to localhost:8000/api/v1/billing/webhook/

# Production webhook endpoint
POST /api/v1/billing/webhook/
```

**Webhook Events:**
- `payment_intent.succeeded` - Payment successful
- `payment_intent.payment_failed` - Payment failed
- `customer.subscription.updated` - Subscription changed
- `invoice.payment_succeeded` - Invoice paid

## Key Points

1. **14-Day Free Trial** (automatic)
   - All new tenants get free trial
   - Card saved but NOT charged during trial
   - First payment after 14 days

2. **Setup Intent = Save Card** (one-time)
   - Customer enters card details
   - Card saved to Stripe customer
   - No charge during trial

3. **Subscription = Backend Managed**
   - Created in Django database
   - Status: 'trialing' during trial, 'active' after
   - Billing periods calculated from trial end

4. **Recurring Charges = Automated**
   - Celery task runs daily
   - Handles trial conversions and renewals
   - Charges saved card automatically
   - No customer interaction needed

5. **Payment Method Saved = `off_session: true`**
   - Allows charging without customer present
   - Required for recurring payments
   - Set during setup intent

## Security

- ✅ Card details never touch your server
- ✅ Stripe.js handles PCI compliance
- ✅ Only payment method ID stored
- ✅ Charges use saved payment method
- ✅ Webhook signatures verified

## Monitoring

Track these metrics:
- Successful renewals
- Failed payments
- Past due subscriptions
- Cancellation rate
- Revenue (MRR/ARR)

## Troubleshooting

### "Card declined"
- Customer's card was declined
- Status → `past_due`
- Retry automatically next day

### "No payment method"
- Customer didn't complete setup intent
- Subscription created but can't charge
- Send email to complete payment setup

### "Stripe not enabled"
- STRIPE_SECRET_KEY not configured
- Subscriptions work without payment
- Add Stripe keys to enable charging

## Summary

**Setup Intent** → Saves card for future use  
**Create Subscription** → Starts billing period  
**Celery Tasks** → Automatically charge monthly/yearly  
**Webhooks** → Real-time payment updates (optional)

Your backend manages everything. Stripe just processes the payments! 🚀
