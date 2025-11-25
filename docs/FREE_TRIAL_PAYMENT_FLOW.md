# Free Trial Payment Flow

## Overview

FieldRino offers a **14-day free trial** for all new tenants. During the trial period, users can add their payment method, but **no charges are made until the trial ends**.

## How It Works

### 1. User Signup & Trial Start
- User creates an account and company (tenant)
- Tenant automatically gets a **14-day free trial** (`trial_ends_at` is set)
- User can explore all features during this period

### 2. Adding Payment Method (During Trial)
- User adds credit card via Stripe
- Card is **saved but NOT charged**
- Subscription is created with `status='trialing'`
- `trial_start` and `trial_end` dates are set on subscription
- `current_period_start` is set to `trial_end` (billing starts after trial)

### 3. Trial End & First Payment
- Daily task `process_subscription_renewals()` runs via Celery Beat
- On trial end date, the task:
  - Charges the saved payment method for the first billing period
  - Creates invoice and payment records
  - Converts subscription from `'trialing'` to `'active'` status
  - Starts the regular billing cycle

### 4. Recurring Payments
- After trial conversion, regular monthly/yearly billing continues
- Same daily task handles renewals at the end of each billing period

## Payment Timing

| Scenario | When Payment is Charged |
|----------|------------------------|
| **With Active Trial** | After 14 days (when trial ends) |
| **Trial Already Expired** | Immediately when card is added |
| **No Trial Set** | Immediately when card is added |

## API Flow

### Create Subscription During Trial

```http
POST /api/billing/subscriptions/
Authorization: Bearer {token}
Content-Type: application/json

{
  "plan_slug": "professional",
  "billing_cycle": "monthly",
  "payment_method_id": "pm_xxxxx"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Subscription created successfully",
  "data": {
    "id": "uuid",
    "status": "trialing",
    "trial_start": "2025-11-25T10:00:00Z",
    "trial_end": "2025-12-09T10:00:00Z",
    "current_period_start": "2025-12-09T10:00:00Z",
    "current_period_end": "2026-01-09T10:00:00Z",
    "is_trial": true,
    "plan": {
      "name": "Professional",
      "price_monthly": 49.00
    }
  }
}
```

**Note:** No charge is made at this point. Payment will be processed on `trial_end` date.

## Code Implementation

### Subscription Creation Logic

```python
# Check if tenant has active trial
is_in_trial = tenant.is_trial_active

if is_in_trial:
    # Trial mode: Don't charge, set trial dates
    subscription_status = 'trialing'
    trial_start = now
    trial_end = tenant.trial_ends_at
    current_period_start = trial_end  # Billing starts after trial
else:
    # No trial: Charge immediately
    subscription_status = 'active'
    trial_start = None
    trial_end = None
    current_period_start = now
```

### Daily Task for Trial Conversion

```python
@shared_task
def process_subscription_renewals():
    # Find subscriptions where trial ends today
    subscriptions_trial_ending = Subscription.objects.filter(
        trial_end__date=today,
        status='trialing'
    )
    
    for subscription in subscriptions_trial_ending:
        # Charge customer for first billing period
        charge = StripeService.charge_customer(...)
        
        # Create invoice and payment records
        invoice = Invoice.objects.create(...)
        Payment.objects.create(...)
        
        # Convert to active
        subscription.status = 'active'
        subscription.save()
```

## Celery Beat Schedule

The trial conversion and renewal task should run daily:

```python
# config/celery.py
CELERY_BEAT_SCHEDULE = {
    'process-subscription-renewals': {
        'task': 'apps.billing.tasks.process_subscription_renewals',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
```

## User Experience

### Timeline Example

**Day 0 (Nov 25):**
- User signs up
- Trial starts, expires on Dec 9

**Day 3 (Nov 28):**
- User adds credit card
- Card saved, no charge
- Message: "Your card will be charged $49.00 on Dec 9, 2025"

**Day 14 (Dec 9):**
- Trial ends
- First payment of $49.00 charged automatically
- Subscription becomes active
- Email sent: "Your trial has ended, first payment processed"

**Day 44 (Jan 9, 2026):**
- Regular renewal
- Next payment of $49.00 charged
- Email sent: "Your subscription has been renewed"

## Benefits

1. **True Free Trial**: Users can fully test the platform without payment
2. **Seamless Conversion**: Automatic transition from trial to paid
3. **No Surprises**: Users know exactly when they'll be charged
4. **Better Conversion**: Lower friction during signup
5. **Reduced Support**: Clear payment timeline reduces confusion

## Testing

### Test Trial Flow

1. Create tenant (trial starts automatically)
2. Add payment method via `/api/billing/setup-intent/`
3. Create subscription with payment method
4. Verify subscription status is `'trialing'`
5. Verify no charge was made
6. Manually run task or wait for trial end
7. Verify charge is processed and status changes to `'active'`

### Test Without Trial

1. Create tenant
2. Manually expire trial: `tenant.trial_ends_at = timezone.now() - timedelta(days=1)`
3. Add payment method and create subscription
4. Verify immediate charge
5. Verify subscription status is `'active'`

## Related Files

- `apps/billing/views.py` - Subscription creation logic
- `apps/billing/tasks.py` - Trial conversion and renewal task
- `apps/billing/models.py` - Subscription model with trial fields
- `apps/tenants/models.py` - Tenant model with trial tracking
- `apps/tenants/views.py` - Trial initialization during onboarding
