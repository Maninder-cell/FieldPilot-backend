"""
Tasks Tests

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.test import TestCase
from django.utils import timezone
from apps.authentication.models import User
from apps.equipment.models import Equipment
from apps.facilities.models import Facility, Building
from .models import Task, TechnicianTeam, TaskAssignment, TimeLog
from .utils import SiteConflictValidator, WorkHoursCalculator, TaskStatusValidator


class TaskModelTest(TestCase):
    """Test Task model functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        self.technician = User.objects.create_user(
            email='tech@test.com',
            password='test123',
            first_name='Tech',
            last_name='User',
            role='technician'
        )
        
        # Create facility and building
        self.facility = Facility.objects.create(
            name='Test Facility',
            created_by=self.admin
        )
        
        self.building = Building.objects.create(
            facility=self.facility,
            name='Test Building',
            created_by=self.admin
        )
        
        # Create equipment
        self.equipment = Equipment.objects.create(
            building=self.building,
            name='Test Equipment',
            created_by=self.admin
        )
    
    def test_task_creation(self):
        """Test task creation with auto-generated task number."""
        task = Task.objects.create(
            equipment=self.equipment,
            title='Test Task',
            description='Test description',
            priority='high',
            created_by=self.admin
        )
        
        self.assertIsNotNone(task.task_number)
        self.assertTrue(task.task_number.startswith('TASK-'))
        self.assertEqual(task.status, 'new')
        self.assertEqual(task.priority, 'high')
    
    def test_task_assignment(self):
        """Test task assignment to technician."""
        task = Task.objects.create(
            equipment=self.equipment,
            title='Test Task',
            description='Test description',
            created_by=self.admin
        )
        
        assignment = TaskAssignment.objects.create(
            task=task,
            assignee=self.technician,
            assigned_by=self.admin
        )
        
        self.assertEqual(assignment.work_status, 'open')
        self.assertEqual(assignment.assignee, self.technician)
    
    def test_team_creation(self):
        """Test technician team creation."""
        team = TechnicianTeam.objects.create(
            name='Test Team',
            description='Test team description',
            created_by=self.admin
        )
        
        team.members.add(self.technician)
        
        self.assertEqual(team.member_count, 1)
        self.assertTrue(team.is_active)


class SiteConflictValidatorTest(TestCase):
    """Test site conflict validation."""
    
    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        self.technician = User.objects.create_user(
            email='tech@test.com',
            password='test123',
            first_name='Tech',
            last_name='User',
            role='technician'
        )
        
        self.facility = Facility.objects.create(
            name='Test Facility',
            created_by=self.admin
        )
        
        self.building = Building.objects.create(
            facility=self.facility,
            name='Test Building',
            created_by=self.admin
        )
        
        self.equipment = Equipment.objects.create(
            building=self.building,
            name='Test Equipment',
            created_by=self.admin
        )
        
        self.task = Task.objects.create(
            equipment=self.equipment,
            title='Test Task',
            description='Test description',
            created_by=self.admin
        )
    
    def test_can_travel_when_not_on_site(self):
        """Test technician can travel when not on any site."""
        can_travel, message = SiteConflictValidator.can_travel(self.technician)
        self.assertTrue(can_travel)
        self.assertIsNone(message)
    
    def test_cannot_travel_when_on_site(self):
        """Test technician cannot travel when already on a site."""
        # Create time log (technician on site)
        TimeLog.objects.create(
            task=self.task,
            technician=self.technician,
            travel_started_at=timezone.now(),
            arrived_at=timezone.now()
        )
        
        can_travel, message = SiteConflictValidator.can_travel(self.technician)
        self.assertFalse(can_travel)
        self.assertIsNotNone(message)


class WorkHoursCalculatorTest(TestCase):
    """Test work hours calculation."""
    
    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        self.technician = User.objects.create_user(
            email='tech@test.com',
            password='test123',
            first_name='Tech',
            last_name='User',
            role='technician'
        )
        
        self.facility = Facility.objects.create(
            name='Test Facility',
            created_by=self.admin
        )
        
        self.building = Building.objects.create(
            facility=self.facility,
            name='Test Building',
            created_by=self.admin
        )
        
        self.equipment = Equipment.objects.create(
            building=self.building,
            name='Test Equipment',
            created_by=self.admin
        )
        
        self.task = Task.objects.create(
            equipment=self.equipment,
            title='Test Task',
            description='Test description',
            created_by=self.admin
        )
    
    def test_work_hours_calculation(self):
        """Test work hours calculation with lunch break."""
        from datetime import timedelta
        
        now = timezone.now()
        
        time_log = TimeLog.objects.create(
            task=self.task,
            technician=self.technician,
            arrived_at=now,
            departed_at=now + timedelta(hours=9),
            lunch_started_at=now + timedelta(hours=4),
            lunch_ended_at=now + timedelta(hours=5)
        )
        
        total, normal, overtime = WorkHoursCalculator.calculate(time_log)
        
        # 9 hours - 1 hour lunch = 8 hours total
        self.assertEqual(total, 8.0)
        self.assertEqual(normal, 8.0)
        self.assertEqual(overtime, 0.0)
    
    def test_overtime_calculation(self):
        """Test overtime hours calculation."""
        from datetime import timedelta
        
        now = timezone.now()
        
        time_log = TimeLog.objects.create(
            task=self.task,
            technician=self.technician,
            arrived_at=now,
            departed_at=now + timedelta(hours=10)
        )
        
        total, normal, overtime = WorkHoursCalculator.calculate(time_log)
        
        # 10 hours total: 8 normal + 2 overtime
        self.assertEqual(total, 10.0)
        self.assertEqual(normal, 8.0)
        self.assertEqual(overtime, 2.0)


print("✅ Task Management System Tests Created")
print("Run tests with: python manage.py test apps.tasks")
