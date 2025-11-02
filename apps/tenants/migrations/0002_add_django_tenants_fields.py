# Generated migration for django-tenants integration

from django.db import migrations, models
import django.db.models.deletion
import django_tenants.postgresql_backend.base


def populate_schema_names(apps, schema_editor):
    """Populate schema_name for existing tenants"""
    Tenant = apps.get_model('tenants', 'Tenant')
    for tenant in Tenant.objects.all():
        # Generate schema_name from slug
        tenant.schema_name = tenant.slug.replace('-', '_').lower()
        tenant.save()


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        # Step 1: Add schema_name field without unique constraint
        migrations.AddField(
            model_name="tenant",
            name="schema_name",
            field=models.CharField(
                db_index=True,
                max_length=63,
                null=True,
                blank=True,
                validators=[django_tenants.postgresql_backend.base._check_schema_name],
            ),
        ),
        # Step 2: Populate schema_name from slug for existing records
        migrations.RunPython(populate_schema_names, migrations.RunPython.noop),
        # Step 3: Make schema_name non-nullable and unique
        migrations.AlterField(
            model_name="tenant",
            name="schema_name",
            field=models.CharField(
                db_index=True,
                max_length=63,
                unique=True,
                validators=[django_tenants.postgresql_backend.base._check_schema_name],
            ),
        ),
        # Step 4: Create Domain model
        migrations.CreateModel(
            name="Domain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "domain",
                    models.CharField(db_index=True, max_length=253, unique=True),
                ),
                ("is_primary", models.BooleanField(db_index=True, default=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="domains",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Domain",
                "verbose_name_plural": "Domains",
                "db_table": "tenants_domains",
            },
        ),
    ]
