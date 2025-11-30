"""
Management command to verify tenant role migration.

Usage:
    python manage.py verify_tenant_roles
"""
from django.core.management.base import BaseCommand
from django.db import connection
from apps.tenants.models import Tenant, TenantMember
from apps.authentication.models import User


class Command(BaseCommand):
    help = 'Verify tenant role migration and multi-tenant setup'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Verifying Multi-Tenant Role Setup\n'))
        
        # Switch to public schema
        connection.set_schema_to_public()
        
        # Check tenants
        tenant_count = Tenant.objects.count()
        self.stdout.write(f'📊 Total Tenants: {tenant_count}')
        
        # Check users
        user_count = User.objects.count()
        self.stdout.write(f'👥 Total Users: {user_count}')
        
        # Check tenant members
        member_count = TenantMember.objects.count()
        self.stdout.write(f'🔗 Total Tenant Members: {member_count}\n')
        
        # Check for users with multiple memberships
        users_with_multiple_tenants = []
        for user in User.objects.all():
            memberships = TenantMember.objects.filter(user=user, is_active=True)
            if memberships.count() > 1:
                users_with_multiple_tenants.append({
                    'user': user,
                    'count': memberships.count(),
                    'memberships': memberships
                })
        
        if users_with_multiple_tenants:
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Found {len(users_with_multiple_tenants)} users with multiple tenant memberships:'
            ))
            for item in users_with_multiple_tenants:
                self.stdout.write(f'\n  👤 {item["user"].email} ({item["count"]} tenants):')
                for membership in item['memberships']:
                    self.stdout.write(
                        f'     - {membership.tenant.name}: {membership.role} '
                        f'(Employee ID: {membership.employee_id or "N/A"})'
                    )
        else:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  No users with multiple tenant memberships found'
            ))
        
        # Check role distribution
        self.stdout.write(self.style.SUCCESS('\n📈 Role Distribution:'))
        role_counts = {}
        for member in TenantMember.objects.filter(is_active=True):
            role_counts[member.role] = role_counts.get(member.role, 0) + 1
        
        for role, count in sorted(role_counts.items()):
            self.stdout.write(f'  {role}: {count}')
        
        # Check for members without employee_id
        members_without_employee_id = TenantMember.objects.filter(
            is_active=True,
            employee_id=''
        ).count()
        
        if members_without_employee_id > 0:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  {members_without_employee_id} members without employee_id'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ All members have employee_id'
            ))
        
        # Check for orphaned users (users without any tenant membership)
        orphaned_users = []
        for user in User.objects.all():
            if not TenantMember.objects.filter(user=user, is_active=True).exists():
                orphaned_users.append(user)
        
        if orphaned_users:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  Found {len(orphaned_users)} users without tenant membership:'
            ))
            for user in orphaned_users[:10]:  # Show first 10
                self.stdout.write(f'  - {user.email}')
            if len(orphaned_users) > 10:
                self.stdout.write(f'  ... and {len(orphaned_users) - 10} more')
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ All users have at least one tenant membership'
            ))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✨ Verification Complete!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Recommendations
        self.stdout.write('\n📝 Recommendations:')
        if members_without_employee_id > 0:
            self.stdout.write('  - Run migration to generate employee IDs')
        if orphaned_users:
            self.stdout.write('  - Review orphaned users and assign to tenants')
        if not users_with_multiple_tenants:
            self.stdout.write('  - Test multi-tenant functionality by adding users to multiple tenants')
        
        self.stdout.write('')
