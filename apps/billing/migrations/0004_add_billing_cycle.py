# Generated migration to add billing_cycle field back

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_stripe_migration"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="billing_cycle",
            field=models.CharField(
                max_length=20,
                choices=[
                    ('monthly', 'Monthly'),
                    ('yearly', 'Yearly'),
                ],
                default='monthly'
            ),
        ),
    ]
