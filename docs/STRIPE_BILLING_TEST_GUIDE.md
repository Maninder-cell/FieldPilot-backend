# Stripe Billing Test Guide

## Testing Subscription Billing Cycle Updates

### Current Implementation

The system fetches billing data from Stripe in real-time:

1. **API Endpoint**: `GET /api/v1/billing/subscription/current/`
   - Fetches latest subscription data from Stripe on every request
   - Returns: `current_period_start`, `current_period_end`, `trial_end`, etc.

2. **Webhook Sync**: Automatic updates via Stripe webhooks
   - `customer.subscription.updated` - Updates subscription status
   - `invoice.payment_succeeded` - Confirms successful payments
   - `invoice.payment_failed` - Marks subscription as past_due

### How to Test Billing Cycle Simulation

#### Step 1: Find Your Subscription in Stripe Dashboard

1. Go to: https://dashboard.stripe.com/test/subscriptions
2. Make sure you're in **Test mode**
3. Find subscription: `sub_1SYR38Afo5hcOfdYvbbrjNcH` (or your latest one)

#### Step 2: Simulate Billing in Stripe

**Option A: Advance Subscription to Next Billing Period**
1. Open the subscription in Stripe Dashboard
2. Click the "..." menu (top right)
3. Select "Advance subscription"
4. Choose "Advance to next billing period"
5. Confirm

**Option B: Use Stripe CLI**
```bash
stripe subscriptions update sub_1SYR38Afo5hcOfdYvbbrjNcH \
  --trial-end now
```

#### Step 3: Verify Data is Fetched

**Test 1: Check via API**
```bash
# Get current subscription
curl -X GET http://localhost:8000/api/v1/billing/subscription/current/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Expected response should show:
- `current_period_start`: Updated timestamp
- `current_period_end`: Updated timestamp  
- `status`: "active" (changed from "trialing")
- `trial_end`: The trial end date

**Test 2: Check Database**
```bash
docker exec fieldrino_postgres psql -U fieldrino_user -d fieldrino_db \
  -c "SELECT id, status, created_at, updated_at FROM billing_subscriptions;"
```

The `status` field should be updated by webhooks.

### What Gets Updated Automatically

✅ **Via API (Real-time from Stripe)**:
- `current_period_start`
- `current_period_end`
- `trial_start` / `trial_end`
- `cancel_at_period_end`
- `canceled_at`
- Billing cycle information

✅ **Via Webhooks (Stored in Database)**:
- `status` (trialing → active → past_due → canceled)

### Webhook Testing

To test webhooks locally:

1. **Install Stripe CLI**: https://stripe.com/docs/stripe-cli

2. **Forward webhooks to local server**:
```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook/
```

3. **Trigger test events**:
```bash
# Test subscription updated
stripe trigger customer.subscription.updated

# Test payment succeeded
stripe trigger invoice.payment_succeeded

# Test payment failed
stripe trigger invoice.payment_failed
```

### Expected Behavior After Billing Simulation

1. **Immediately after simulation**:
   - Stripe subscription updated
   - Webhook sent to your server
   - Local `status` field updated

2. **When you call the API**:
   - Fresh data fetched from Stripe
   - Returns latest `current_period_start` and `current_period_end`
   - Shows updated billing cycle dates

### Troubleshooting

**If dates don't update:**
1. Check Stripe Dashboard - verify the subscription was actually updated
2. Check API response - it should fetch from Stripe directly
3. Check logs for Stripe API calls:
   ```bash
   docker logs fieldrino_web | grep "Stripe API"
   ```

**If webhooks don't work:**
1. Verify webhook endpoint is accessible
2. Check webhook secret in `.env`: `STRIPE_WEBHOOK_SECRET`
3. Check webhook logs in Stripe Dashboard
4. Use Stripe CLI to forward webhooks locally

### Code References

- **Serializer**: `apps/billing/serializers.py` - `SubscriptionSerializer._get_stripe_subscription()`
- **View**: `apps/billing/views.py` - `current_subscription()`
- **Webhooks**: `apps/billing/views.py` - `stripe_webhook()` and handlers
- **Stripe Service**: `apps/billing/stripe_service.py` - `get_subscription()`

## Summary

✅ **Yes, the current code will fetch the latest billing dates from Stripe**

The system uses a hybrid approach:
- **Critical billing data** (dates, amounts) → Fetched from Stripe in real-time
- **Status updates** → Synced via webhooks and stored locally
- **Usage tracking** → Stored locally only

This ensures you always have accurate billing information while minimizing API calls.
