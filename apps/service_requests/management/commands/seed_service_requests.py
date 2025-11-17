"""
Seed Service Requests Data

Task 25: Create deployment scripts - Data seeding script
Management command to seed sample service request data for testing.

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from apps.service_requests.models import ServiceRequest, RequestAction, RequestComment
from apps.authentication.models import User
from apps.equipment.models import Equipment


class Command(BaseCommand):
    help = 'Seed sample service request data for testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of service requests to create'
        )
        
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing service requests before seeding'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']
        
        if clear:
            self.stdout.write('Clearing existing service requests...')
            ServiceRequest.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing data'))
        
        # Get users
        customers = User.objects.filter(role='customer')
        admins = User.objects.filter(role__in=['admin', 'manager'])
        
        if not customers.exists():
            self.stdout.write(self.style.ERROR('No customers found. Please create customer users first.'))
            return
        
        if not admins.exists():
            self.stdout.write(self.style.ERROR('No admins found. Please create admin users first.'))
            return
        
        # Get equipment
        equipment_list = Equipment.objects.all()
        
        if not equipment_list.exists():
            self.stdout.write(self.style.ERROR('No equipment found. Please create equipment first.'))
            return
        
        self.stdout.write(f'Creating {count} service requests...')
        
        request_types = ['service', 'issue', 'maintenance', 'inspection']
        priorities = ['low', 'medium', 'high', 'urgent']
        statuses = ['pending', 'under_review', 'accepted', 'rejected', 'in_progress', 'completed']
        issue_types = ['breakdown', 'malfunction', 'safety', 'performance', 'other']
        severities = ['minor', 'moderate', 'major', 'critical']
        
        created_count = 0
        
        for i in range(count):
            customer = random.choice(customers)
            equipment = random.choice(equipment_list)
            request_type = random.choice(request_types)
            priority = random.choice(priorities)
            status = random.choice(statuses)
            
            # Create service request
            request_data = {
                'customer': customer,
                'equipment': equipment,
                'facility': equipment.facility,
                'request_type': request_type,
                'title': f'Sample {request_type.title()} Request #{i+1}',
                'description': f'This is a sample {request_type} request for testing purposes.',
                'priority': priority,
                'status': status,
            }
            
            # Add issue-specific fields
            if request_type == 'issue':
                request_data['issue_type'] = random.choice(issue_types)
                request_data['severity'] = random.choice(severities)
            
            # Add review data for non-pending requests
            if status != 'pending':
                admin = random.choice(admins)
                request_data['reviewed_by'] = admin
                request_data['reviewed_at'] = timezone.now() - timedelta(days=random.randint(1, 30))
                
                if status == 'accepted':
                    request_data['response_message'] = 'Request accepted and will be processed soon.'
                    request_data['estimated_timeline'] = f'{random.randint(1, 5)} days'
                    request_data['estimated_cost'] = random.uniform(100, 1000)
                
                elif status == 'rejected':
                    request_data['rejection_reason'] = 'This service is not covered under your current plan.'
            
            # Add completion data for completed requests
            if status == 'completed':
                request_data['completed_at'] = timezone.now() - timedelta(days=random.randint(1, 15))
                request_data['customer_rating'] = random.randint(3, 5)
                request_data['customer_feedback'] = 'Great service, very professional!'
                request_data['feedback_submitted_at'] = timezone.now() - timedelta(days=random.randint(1, 10))
            
            # Set created_at to past date
            created_at = timezone.now() - timedelta(days=random.randint(1, 60))
            
            service_request = ServiceRequest(**request_data)
            service_request.save()
            
            # Update created_at manually
            ServiceRequest.objects.filter(id=service_request.id).update(created_at=created_at)
            
            # Create action log
            RequestAction.log_action(
                request=service_request,
                action_type='created',
                user=customer,
                description=f'Service request created by {customer.get_full_name()}',
                metadata={
                    'request_type': request_type,
                    'priority': priority,
                }
            )
            
            # Add some comments
            if random.random() > 0.5:
                RequestComment.objects.create(
                    request=service_request,
                    user=customer,
                    comment_text='Looking forward to getting this resolved.',
                    is_internal=False,
                )
            
            if status != 'pending' and random.random() > 0.5:
                admin = request_data.get('reviewed_by')
                if admin:
                    RequestComment.objects.create(
                        request=service_request,
                        user=admin,
                        comment_text='We are working on this request.',
                        is_internal=False,
                    )
            
            created_count += 1
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f'Created {i + 1}/{count} requests...')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} service requests')
        )
