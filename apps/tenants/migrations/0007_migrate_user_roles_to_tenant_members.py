# Data migration to copy user roles to tenant members

from django.db import migrations


def migrate_user_roles_to_tenant_members(apps, schema_editor):
    """
    Generate employee IDs for existing tenant members.
    User model no longer has role/employee_id fields.
    """
    TenantMember = apps.get_model('tenants', 'TenantMember')
    
    updated_count = 0
    
    for member in TenantMember.objects.all():
        # Generate employee_id if not set
        if not member.employee_id:
            member.generate_employee_id()
            member.save()
            updated_count += 1
    
    print(f"✅ Generated employee IDs for {updated_count} tenant members")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - no action needed as we don't want to lose data.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0006_add_employee_fields_to_tenant_member'),
        ('authentication', '0001_initial'),  # Ensure User model exists
    ]

    operations = [
        migrations.RunPython(
            migrate_user_roles_to_tenant_members,
            reverse_migration
        ),
    ]
