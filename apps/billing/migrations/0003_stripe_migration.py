# Generated migration for Stripe billing migration

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_alter_subscription_stripe_customer_id_and_more"),
    ]

    operations = [
        # Remove obsolete fields from Subscription model
        migrations.RemoveField(
            model_name="subscription",
            name="billing_cycle",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="current_period_start",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="current_period_end",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="cancel_at_period_end",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="canceled_at",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="trial_start",
        ),
        migrations.RemoveField(
            model_name="subscription",
            name="trial_end",
        ),
        
        # Make Stripe ID fields NOT NULL (with default for existing records)
        migrations.AlterField(
            model_name="subscription",
            name="stripe_customer_id",
            field=models.CharField(max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="subscription",
            name="stripe_subscription_id",
            field=models.CharField(max_length=255, unique=True, default=''),
            preserve_default=False,
        ),
        
        # Add indexes on Stripe ID fields
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["stripe_customer_id"], name="billing_sub_stripe_c_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["stripe_subscription_id"], name="billing_sub_stripe_s_idx"),
        ),
        
        # Drop obsolete tables
        migrations.DeleteModel(
            name="UsageRecord",
        ),
        migrations.DeleteModel(
            name="Payment",
        ),
        migrations.DeleteModel(
            name="Invoice",
        ),
    ]
