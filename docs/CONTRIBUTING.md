# Contributing to FieldRino

Thank you for your interest in contributing to FieldRino! This document provides guidelines and instructions for contributing to the project.

## ⚠️ Important: Proprietary Software Notice

**FieldRino is proprietary software.** All source code and associated files are the intellectual property of FieldRino and protected by copyright law.

### What This Means for Contributors

- **Internal Team Only**: Contributions are accepted only from authorized team members
- **No Public Contributions**: This is NOT an open-source project
- **Confidentiality**: All code, documentation, and project information is confidential
- **Copyright**: All contributions become the property of FieldRino
- **No Redistribution**: You may NOT copy, distribute, or share any part of this codebase

### Licensing

By contributing to this project, you agree that:
1. Your contributions will be owned by FieldRino
2. You will not share, copy, or distribute any code or documentation
3. You understand this is proprietary software with all rights reserved
4. You have read and agree to the terms in the LICENSE file

For licensing inquiries, contact: legal@fieldrino.com

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of experience level, gender, gender identity and expression, sexual orientation, disability, personal appearance, body size, race, ethnicity, age, religion, or nationality.

### Expected Behavior

- Be respectful and considerate
- Welcome newcomers and help them get started
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

Before contributing, ensure you have:
- Read the [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- Set up your development environment
- Familiarized yourself with the codebase
- Reviewed open issues and pull requests

### Finding Issues to Work On

1. Check the [GitHub Issues](https://github.com/your-org/fieldrino/issues)
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to express interest
4. Wait for assignment before starting work

### Setting Up Your Development Environment

```bash
# Fork the repository
# Clone your fork
git clone https://github.com/YOUR_USERNAME/fieldrino.git
cd fieldrino

# Add upstream remote
git remote add upstream https://github.com/your-org/fieldrino.git

# Create a new branch
git checkout -b feature/your-feature-name

# Set up development environment
# See DEVELOPMENT_GUIDE.md for detailed instructions
```

## Development Workflow

### 1. Create a Branch

```bash
# Feature branch
git checkout -b feature/equipment-qr-scanning

# Bug fix branch
git checkout -b fix/task-assignment-bug

# Documentation branch
git checkout -b docs/update-api-docs
```

### Branch Naming Convention

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or updates
- `chore/` - Maintenance tasks

### 2. Make Changes

- Write clean, readable code
- Follow coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Test Your Changes

```bash
# Backend tests
cd backend
python manage.py test
coverage run --source='.' manage.py test
coverage report

# Frontend tests
cd frontend
npm run test
npm run test:coverage

# Linting
cd backend
black .
flake8 .

cd frontend
npm run lint
npm run format
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add QR code scanning for equipment"
```

### 5. Push to Your Fork

```bash
git push origin feature/equipment-qr-scanning
```

### 6. Create Pull Request

- Go to GitHub and create a pull request
- Fill out the PR template completely
- Link related issues
- Request review from maintainers

## Coding Standards

### Python (Backend)

#### Style Guide

Follow PEP 8 with these specifics:
- Line length: 88 characters (Black default)
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes

```python
from typing import List, Optional
from apps.equipment.models import Equipment

def calculate_health_score(
    equipment: Equipment,
    maintenance_records: List[MaintenanceRecord],
    threshold: int = 80
) -> int:
    """
    Calculate equipment health score based on maintenance history.
    
    Args:
        equipment: Equipment instance to evaluate
        maintenance_records: List of maintenance records
        threshold: Minimum acceptable health score (default: 80)
        
    Returns:
        Health score between 0-100
        
    Raises:
        ValueError: If equipment is None or maintenance_records is empty
    """
    if equipment is None:
        raise ValueError("Equipment cannot be None")
    
    # Implementation
    return health_score
```

#### Code Organization

```python
# Standard library imports
import os
import sys
from datetime import datetime

# Third-party imports
from django.db import models
from rest_framework import serializers

# Local imports
from apps.core.models import BaseModel
from apps.equipment.utils import generate_equipment_number
```

#### Django Best Practices

```python
# Use select_related for foreign keys
equipment = Equipment.objects.select_related('facility', 'building').get(id=equipment_id)

# Use prefetch_related for reverse relations
facilities = Facility.objects.prefetch_related('equipment_set').all()

# Use Q objects for complex queries
from django.db.models import Q
equipment = Equipment.objects.filter(
    Q(status='operational') | Q(status='maintenance')
)

# Use F expressions for database-level operations
from django.db.models import F
Equipment.objects.filter(id=equipment_id).update(
    operational_hours=F('operational_hours') + 1
)
```

### TypeScript (Frontend)

#### Style Guide

- Use TypeScript for all new code
- Define interfaces for all data structures
- Use functional components with hooks
- Prefer const over let, never use var

```typescript
// Define interfaces
interface Equipment {
  id: string;
  name: string;
  status: 'operational' | 'maintenance' | 'shutdown';
  healthScore: number;
  facility: {
    id: string;
    name: string;
  };
}

// Component with proper typing
interface EquipmentCardProps {
  equipment: Equipment;
  onSelect: (id: string) => void;
  className?: string;
}

export const EquipmentCard: React.FC<EquipmentCardProps> = ({
  equipment,
  onSelect,
  className = ''
}) => {
  const handleClick = () => {
    onSelect(equipment.id);
  };

  return (
    <div className={`rounded-lg border p-4 ${className}`} onClick={handleClick}>
      <h3 className="text-lg font-semibold">{equipment.name}</h3>
      <p className="text-sm text-gray-600">Status: {equipment.status}</p>
      <div className="mt-2">
        <span className="text-xs">Health: {equipment.healthScore}%</span>
      </div>
    </div>
  );
};
```

#### React Best Practices

```typescript
// Use custom hooks for data fetching
export function useEquipment(id: string) {
  return useQuery({
    queryKey: ['equipment', id],
    queryFn: () => fetchEquipment(id),
    staleTime: 5 * 60 * 1000,
  });
}

// Use memo for expensive computations
const sortedEquipment = useMemo(() => {
  return equipment.sort((a, b) => b.healthScore - a.healthScore);
}, [equipment]);

// Use callback for event handlers
const handleSubmit = useCallback((data: FormData) => {
  createEquipment(data);
}, [createEquipment]);

// Proper error handling
const { data, error, isLoading } = useEquipment(id);

if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorMessage error={error} />;
if (!data) return <NotFound />;

return <EquipmentDetails equipment={data} />;
```

## Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Feature
git commit -m "feat(equipment): add QR code scanning functionality"

# Bug fix
git commit -m "fix(tasks): resolve task assignment notification bug"

# Documentation
git commit -m "docs(api): update equipment endpoint documentation"

# With body
git commit -m "feat(equipment): add health score calculation

Implement algorithm to calculate equipment health based on:
- Maintenance frequency
- Downtime history
- Age of equipment
- Recent issues

Closes #123"
```

### Commit Best Practices

- Keep commits atomic (one logical change per commit)
- Write clear, descriptive commit messages
- Reference issue numbers when applicable
- Don't commit commented-out code
- Don't commit debug statements
- Don't commit sensitive information

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Commit messages follow guidelines
- [ ] PR description is complete

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #123

## Testing
Describe testing performed

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Code Review**: At least one maintainer reviews the code
3. **Feedback**: Address review comments
4. **Approval**: Maintainer approves the PR
5. **Merge**: Maintainer merges the PR

### After Merge

- Delete your feature branch
- Update your local repository
- Close related issues

```bash
# Update your fork
git checkout main
git pull upstream main
git push origin main

# Delete feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

## Testing Requirements

### Backend Testing

```python
# Unit tests
from django.test import TestCase
from apps.equipment.models import Equipment

class EquipmentModelTest(TestCase):
    def setUp(self):
        self.equipment = Equipment.objects.create(
            name="Test Equipment",
            equipment_type="HVAC"
        )
    
    def test_equipment_creation(self):
        self.assertEqual(self.equipment.name, "Test Equipment")
        self.assertIsNotNone(self.equipment.equipment_number)
    
    def test_health_score_default(self):
        self.assertEqual(self.equipment.health_score, 100)

# API tests
from rest_framework.test import APITestCase
from rest_framework import status

class EquipmentAPITest(APITestCase):
    def test_create_equipment(self):
        data = {
            'name': 'New Equipment',
            'equipment_type': 'HVAC'
        }
        response = self.client.post('/api/v1/equipment/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
```

### Frontend Testing

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { EquipmentCard } from './EquipmentCard';

describe('EquipmentCard', () => {
  const mockEquipment = {
    id: '123',
    name: 'Test Equipment',
    status: 'operational' as const,
    healthScore: 85,
    facility: { id: '456', name: 'Test Facility' }
  };

  it('renders equipment name', () => {
    render(<EquipmentCard equipment={mockEquipment} onSelect={jest.fn()} />);
    expect(screen.getByText('Test Equipment')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', () => {
    const onSelect = jest.fn();
    render(<EquipmentCard equipment={mockEquipment} onSelect={onSelect} />);
    
    fireEvent.click(screen.getByText('Test Equipment'));
    expect(onSelect).toHaveBeenCalledWith('123');
  });
});
```

### Test Coverage Requirements

- Minimum 80% coverage for backend
- Minimum 70% coverage for frontend
- 100% coverage for critical paths (authentication, billing)

## Documentation

### Code Documentation

```python
# Python docstrings (Google style)
def calculate_maintenance_cost(
    equipment: Equipment,
    parts: List[Part],
    labor_hours: float
) -> Decimal:
    """
    Calculate total maintenance cost including parts and labor.
    
    Args:
        equipment: Equipment being maintained
        parts: List of parts used
        labor_hours: Hours of labor required
        
    Returns:
        Total cost as Decimal
        
    Raises:
        ValueError: If labor_hours is negative
        
    Example:
        >>> equipment = Equipment.objects.get(id=1)
        >>> parts = [part1, part2]
        >>> cost = calculate_maintenance_cost(equipment, parts, 2.5)
        >>> print(cost)
        Decimal('450.00')
    """
```

```typescript
// TypeScript JSDoc comments
/**
 * Fetches equipment details from the API
 * 
 * @param id - Equipment ID
 * @returns Promise resolving to Equipment object
 * @throws {APIError} If equipment not found or network error
 * 
 * @example
 * ```typescript
 * const equipment = await fetchEquipment('123');
 * console.log(equipment.name);
 * ```
 */
export async function fetchEquipment(id: string): Promise<Equipment> {
  // Implementation
}
```

### Documentation Updates

When making changes, update:
- Code comments and docstrings
- README files (if setup changed)
- Architecture docs (if structure changed)
- User guides (if features changed)
- Ensure all copyright notices remain intact

## Questions?

If you have questions:
1. Check existing documentation
2. Ask in team Slack channel
3. Contact your team lead
4. Email: dev@fieldrino.com

## Confidentiality Reminder

- Do NOT share code or documentation outside the team
- Do NOT commit sensitive information (API keys, passwords, etc.)
- Do NOT discuss project details publicly
- Do NOT use company code for personal projects

## Recognition

Internal team contributors will be recognized in:
- Internal team acknowledgments
- Performance reviews
- Team meetings

---

**Remember: This is proprietary software. Treat all code and documentation as confidential.**

Thank you for being part of the FieldRino team! 🚀
