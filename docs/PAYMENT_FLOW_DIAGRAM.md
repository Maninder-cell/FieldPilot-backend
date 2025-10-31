# Payment Flow Diagram

## Complete Subscription & Payment Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER JOURNEY                                 │
└─────────────────────────────────────────────────────────────────────┘

STEP 1: SAVE PAYMENT METHOD (One-time)
═══════════════════════════════════════

Frontend                    Backend                     Stripe
────────                    ───────                     ──────
   │                           │                           │
   │  POST /setup-intent/      │                           │
   ├──────────────────────────>│                           │
   │                           │  Create Customer          │
   │                           ├──────────────────────────>│
   │                           │  customer_id: cus_xxx     │
   │                           │<──────────────────────────┤
   │                           │  Create SetupIntent       │
   │                           ├──────────────────────────>│
   │  client_secret            │  client_secret            │
   │<──────────────────────────┤<──────────────────────────┤
   │                           │                           │
   │  [User enters card]       │                           │
   │  Stripe.js                │                           │
   │  confirmCardSetup()       │                           │
   ├───────────────────────────────────────────────────────>│
   │                           │                           │
   │                           │  Card saved!              │
   │  payment_method_id        │  pm_xxx                   │
   │<───────────────────────────────────────────────────────┤
   │                           │                           │


STEP 2: CREATE SUBSCRIPTION
════════════════════════════

Frontend                    Backend                     Stripe
────────                    ───────                     ──────
   │                           │                           │
   │  POST /subscription/      │                           │
   │  create/                  │                           │
   │  {                        │                           │
   │    plan_slug,             │                           │
   │    billing_cycle,         │                           │
   │    payment_method_id      │                           │
   │  }                        │                           │
   ├──────────────────────────>│                           │
   │                           │                           │
   │                           │  1. Create in DB          │
   │                           │  2. Link to customer      │
   │                           │  3. Set billing period    │
   │                           │     (30 or 365 days)      │
   │                           │                           │
   │  Subscription created     │                           │
   │  Status: active           │                           │
   │<──────────────────────────┤                           │
   │                           │                           │


STEP 3: RECURRING CHARGES (Automated - No user interaction)
════════════════════════════════════════════════════════════

Celery Beat                 Backend                     Stripe
───────────                 ───────                     ──────
   │                           │                           │
   │  Daily at 2:00 AM         │                           │
   │  Trigger renewal task     │                           │
   ├──────────────────────────>│                           │
   │                           │                           │
   │                           │  Find subscriptions       │
   │                           │  ending today             │
   │                           │                           │
   │                           │  For each subscription:   │
   │                           │  ─────────────────────    │
   │                           │  Calculate amount         │
   │                           │  ($79 for monthly)        │
   │                           │                           │
   │                           │  Charge customer          │
   │                           │  PaymentIntent.create()   │
   │                           ├──────────────────────────>│
   │                           │                           │
   │                           │                           │
   │                           │  [Stripe charges card]    │
   │                           │                           │
   │                           │  Payment successful       │
   │                           │  charge_id: ch_xxx        │
   │                           │<──────────────────────────┤
   │                           │                           │
   │                           │  1. Create invoice        │
   │                           │  2. Create payment record │
   │                           │  3. Extend period         │
   │                           │     +30 days              │
   │                           │  4. Status: active        │
   │                           │                           │
   │  Renewal complete         │                           │
   │<──────────────────────────┤                           │
   │                           │                           │


PAYMENT FAILURE SCENARIO
════════════════════════

Celery Beat                 Backend                     Stripe
───────────                 ───────                     ──────
   │                           │                           │
   │  Trigger renewal          │                           │
   ├──────────────────────────>│                           │
   │                           │  Charge customer          │
   │                           ├──────────────────────────>│
   │                           │                           │
   │                           │  ❌ Card declined         │
   │                           │<──────────────────────────┤
   │                           │                           │
   │                           │  1. Status: past_due      │
   │                           │  2. Create failed payment │
   │                           │  3. Send email to user    │
   │                           │                           │
   │  Next day at 3:00 AM      │                           │
   │  Retry failed payments    │                           │
   ├──────────────────────────>│                           │
   │                           │  Try charge again         │
   │                           ├──────────────────────────>│
   │                           │                           │
   │                           │  ✅ Success OR            │
   │                           │  ❌ Failed again          │
   │                           │<──────────────────────────┤
   │                           │                           │
   │                           │  After 3 failures:        │
   │                           │  Status: canceled         │
   │                           │                           │
```

## Key Concepts

### 1. Setup Intent (`off_session: true`)
```javascript
// This is the magic that allows recurring charges
stripe.SetupIntent.create({
  customer: 'cus_xxx',
  usage: 'off_session'  // ← Allows charging without customer present
})
```

### 2. Saved Payment Method
```
Customer (cus_xxx)
  └── Payment Method (pm_xxx)
       └── Card: •••• 4242
```

### 3. Recurring Charge
```python
# Backend charges automatically
stripe.PaymentIntent.create(
    amount=7900,  # $79.00
    customer='cus_xxx',  # Has saved card
    off_session=True,  # Customer not present
    confirm=True  # Charge immediately
)
```

## Timeline Example

```
Day 1 (Oct 31):
  ✓ User creates subscription
  ✓ Card saved to Stripe
  ✓ Period: Oct 31 - Nov 30

Day 30 (Nov 30):
  ✓ Celery task runs at 2:00 AM
  ✓ Charges $79 to saved card
  ✓ New period: Nov 30 - Dec 30

Day 60 (Dec 30):
  ✓ Charges $79 again
  ✓ New period: Dec 30 - Jan 30

... continues automatically every 30 days
```

## What You See in Stripe Dashboard

1. **Customers Tab**
   - Customer: John Doe (cus_xxx)
   - Email: john@example.com
   - Payment Methods: •••• 4242

2. **Payments Tab**
   - $79.00 - Nov 30 - Succeeded
   - $79.00 - Dec 30 - Succeeded
   - $79.00 - Jan 30 - Succeeded

3. **No Subscriptions Tab**
   - Subscriptions managed by your backend
   - Stripe only processes payments

## Summary

**Setup Intent** = Save card once  
**Backend** = Manages subscription lifecycle  
**Celery** = Automatically charges monthly/yearly  
**Stripe** = Just processes the payment  

You control everything! 🎯
