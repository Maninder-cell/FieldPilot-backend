# Generated manually for multi-tenant role management

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0005_alter_domain_domain'),
    ]

    operations = [
        # Add new fields to TenantMember
        migrations.AddField(
            model_name='tenantmember',
            name='employee_id',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='tenantmember',
            name='department',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='tenantmember',
            name='job_title',
            field=models.CharField(blank=True, max_length=100),
        ),
        # Update role choices to include technician and customer
        migrations.AlterField(
            model_name='tenantmember',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Owner'),
                    ('admin', 'Admin'),
                    ('manager', 'Manager'),
                    ('employee', 'Employee'),
                    ('technician', 'Technician'),
                    ('customer', 'Customer'),
                ],
                default='employee',
                max_length=20
            ),
        ),
        # Add indexes for better query performance
        migrations.AddIndex(
            model_name='tenantmember',
            index=models.Index(fields=['tenant', 'user', 'is_active'], name='tenant_memb_tenant__idx'),
        ),
        migrations.AddIndex(
            model_name='tenantmember',
            index=models.Index(fields=['role'], name='tenant_memb_role_idx'),
        ),
        migrations.AddIndex(
            model_name='tenantmember',
            index=models.Index(fields=['employee_id'], name='tenant_memb_employe_idx'),
        ),
    ]
