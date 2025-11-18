# User Registration Flow Analysis & Recommendations

## Current Implementation

### Registration Flow
```
POST /api/v1/auth/register/
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "role": "employee",          ← USER SELECTS ROLE
  "department": "IT",
  "job_title": "Developer"
}
```

### Available Roles
- `admin` - Administrator
- `manager` - Manager
- `employee` - Employee
- `technician` - Technician
- `customer` - Customer

## ❌ PROBLEMS WITH CURRENT APPROACH

### 1. Security Risk
**Issue**: Users can self-assign any role, including `admin`
- Anyone can register as an admin
- No validation or approval process
- Potential for privilege escalation

### 2. Not Industry Standard
**Issue**: CMMS/SaaS applications don't let users choose roles during registration

**Why?**
- Roles determine access levels and permissions
- Should be assigned by organization admins
- Prevents unauthorized access

### 3. Confusing UX
**Issue**: New users don't know which role to select
- What's the difference between employee and technician?
- Should I be a manager or employee?
- Can I change my role later?

### 4. Multi-Tenant Confusion
**Issue**: Roles should be tenant-specific, not global
- User might be admin in one company
- Same user might be employee in another company
- Current design doesn't support this

## ✅ INDUSTRY STANDARD APPROACH

### How Leading CMMS/SaaS Platforms Handle This

#### 1. **ServiceNow, Salesforce, Zendesk**
```
Registration Flow:
1. User signs up (email, name, password only)
2. User verifies email
3. User creates/joins organization
4. Organization owner assigns role
```

#### 2. **Monday.com, Asana, Jira**
```
Registration Flow:
1. User signs up with basic info
2. User creates workspace/organization
3. User becomes owner/admin of their organization
4. User invites team members
5. Owner assigns roles to team members
```

#### 3. **Fiix, UpKeep, Limble (CMMS specific)**
```
Registration Flow:
1. User signs up (basic info only)
2. User creates company/facility
3. User becomes company admin automatically
4. Admin invites technicians/managers
5. Admin assigns roles during invitation
```

## 📋 RECOMMENDED FLOW FOR FIELDRINO

### Option A: Simplified Registration (Recommended)

#### Step 1: Basic Registration
```json
POST /api/v1/auth/register/
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890"
  // NO ROLE - assigned later
}
```
- User is created with default role: `pending` or `member`
- No access to any tenant yet

#### Step 2: Email Verification
```json
POST /api/v1/auth/verify-email/
{
  "email": "user@example.com",
  "otp_code": "123456"
}
```

#### Step 3: Onboarding Choice
User chooses one of two paths:

**Path A: Create New Company**
```json
POST /api/v1/onboarding/create-company/
{
  "company_name": "Acme Corp",
  "industry": "Manufacturing",
  "company_size": "50-200"
}
```
- User automatically becomes `admin` of their company
- Company/tenant is created
- User is assigned to tenant with admin role

**Path B: Join Existing Company**
```json
POST /api/v1/onboarding/join-company/
{
  "invitation_code": "ABC123XYZ",
  "company_domain": "acme"
}
```
- User joins with role specified in invitation
- Role assigned by company admin who sent invite

### Option B: Role-Based Registration (Alternative)

Keep role in registration BUT:

#### 1. Separate Customer Registration
```json
POST /api/v1/auth/register/customer/
{
  "email": "customer@example.com",
  "password": "SecurePass123!",
  "first_name": "Jane",
  "last_name": "Smith",
  "company_name": "Client Corp"
}
```
- Customers register separately
- Different UI/flow for customers
- Limited access (submit service requests only)

#### 2. Employee/Staff Registration
```json
POST /api/v1/auth/register/staff/
{
  "email": "staff@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "invitation_code": "REQUIRED"  ← Must have invitation
}
```
- Requires invitation from company admin
- Role pre-assigned in invitation
- Cannot self-register as staff

## 🎯 RECOMMENDED IMPLEMENTATION

### Phase 1: Immediate Fix (Quick Win)

1. **Remove role from public registration**

   - Set default role to `member` or `pending`
   - Role assigned during onboarding

2. **Add role validation**
   ```python
   def validate_role(self, value):
       # Only allow 'customer' during self-registration
       if value not in ['customer', 'member']:
           raise ValidationError("Invalid role for self-registration")
       return value
   ```

3. **Update API documentation**
   - Remove role from registration examples
   - Add onboarding flow documentation

### Phase 2: Proper Multi-Tenant Flow

#### 1. User Model Changes
```python
class User(AbstractBaseUser):
    # Remove global role field
    # role = models.CharField(...)  ← Remove this
    
    # Add user type instead
    user_type = models.CharField(
        choices=[
            ('staff', 'Staff Member'),      # Internal users
            ('customer', 'Customer'),        # External users
        ],
        default='staff'
    )
```

#### 2. Tenant-Specific Roles
```python
class TenantMembership(models.Model):
    """User's role within a specific tenant"""
    user = models.ForeignKey(User)
    tenant = models.ForeignKey(Tenant)
    role = models.CharField(
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            ('technician', 'Technician'),
            ('employee', 'Employee'),
        ]
    )
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(User, related_name='invitations_sent')
    joined_at = models.DateTimeField(auto_now_add=True)
```

#### 3. Registration Endpoints

**A. Customer Registration (Public)**
```python
@api_view(['POST'])
@permission_classes([AllowAny])
def register_customer(request):
    """
    Public registration for customers.
    Customers can submit service requests.
    """
    # Create user with user_type='customer'
    # No tenant assignment yet
    # Limited permissions
```

**B. Staff Registration (Invitation Only)**
```python
@api_view(['POST'])
@permission_classes([AllowAny])
def register_staff(request):
    """
    Staff registration requires invitation code.
    Role is pre-assigned in invitation.
    """
    invitation_code = request.data.get('invitation_code')
    invitation = Invitation.objects.get(code=invitation_code)
    
    # Create user with role from invitation
    # Assign to tenant
    # Create TenantMembership
```

**C. Company Creation (First User)**
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_company(request):
    """
    Create new company/tenant.
    User becomes owner/admin automatically.
    """
    # Create tenant
    # Create TenantMembership with role='owner'
    # User can now invite others
```

## 🎨 FRONTEND DESIGN FLOW

### Registration Page

#### Option 1: Two-Path Registration
```
┌─────────────────────────────────────┐
│     Welcome to FieldRino            │
│                                     │
│  I want to:                         │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  🏢 Start a New Company     │   │
│  │  (For business owners)      │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  👤 I'm a Customer          │   │
│  │  (Request services)         │   │
│  └─────────────────────────────┘   │
│                                     │
│  Already have an account? Login     │
└─────────────────────────────────────┘
```

#### Option 2: Simple Registration + Onboarding
```
Step 1: Sign Up
┌─────────────────────────────────────┐
│  Create Your Account                │
│                                     │
│  Email:    [________________]       │
│  Password: [________________]       │
│  Name:     [________________]       │
│                                     │
│  [Create Account]                   │
└─────────────────────────────────────┘

Step 2: Verify Email
┌─────────────────────────────────────┐
│  Verify Your Email                  │
│                                     │
│  Enter the code sent to:            │
│  user@example.com                   │
│                                     │
│  Code: [_] [_] [_] [_] [_] [_]     │
│                                     │
│  [Verify]                           │
└─────────────────────────────────────┘

Step 3: Choose Path
┌─────────────────────────────────────┐
│  What brings you here?              │
│                                     │
│  ○ I'm starting a new company       │
│     Set up your organization        │
│                                     │
│  ○ I have an invitation code        │
│     Join an existing company        │
│                                     │
│  ○ I'm a customer                   │
│     Request services                │
│                                     │
│  [Continue]                         │
└─────────────────────────────────────┘
```

### Invitation Flow (For Team Members)

```
Email Invitation:
┌─────────────────────────────────────┐
│  You're invited to join             │
│  Acme Corp on FieldRino             │
│                                     │
│  Role: Technician                   │
│  Invited by: John Doe (Admin)       │
│                                     │
│  [Accept Invitation]                │
└─────────────────────────────────────┘

↓

Registration with Pre-filled Info:
┌─────────────────────────────────────┐
│  Join Acme Corp                     │
│                                     │
│  Email:    john@acme.com (locked)   │
│  Password: [________________]       │
│  Name:     [________________]       │
│                                     │
│  Your role: Technician              │
│                                     │
│  [Create Account & Join]            │
└─────────────────────────────────────┘
```

## 📊 COMPARISON: Current vs Recommended

| Aspect | Current | Recommended |
|--------|---------|-------------|
| **Role Selection** | User chooses | System assigns |
| **Security** | ❌ Anyone can be admin | ✅ Role-based access |
| **UX** | ❌ Confusing | ✅ Clear paths |
| **Multi-tenant** | ❌ Global roles | ✅ Tenant-specific |
| **Industry Standard** | ❌ No | ✅ Yes |
| **Scalability** | ❌ Limited | ✅ Flexible |

## 🚀 MIGRATION PLAN

### Step 1: Add New Fields (Non-breaking)
```python
# Add to User model
user_type = models.CharField(default='staff')

# Create TenantMembership model
class TenantMembership(models.Model):
    user = models.ForeignKey(User)
    tenant = models.ForeignKey(Tenant)
    role = models.CharField(...)
```

### Step 2: Create New Endpoints
- `/api/v1/auth/register/` - Basic registration (no role)
- `/api/v1/onboarding/create-company/` - Create company
- `/api/v1/onboarding/join-company/` - Join with invitation
- `/api/v1/invitations/send/` - Send team invitations

### Step 3: Deprecate Old Flow
- Keep old endpoint for backward compatibility
- Add deprecation warning
- Update documentation

### Step 4: Data Migration
```python
# Migrate existing users
for user in User.objects.all():
    # Create TenantMembership for existing users
    # Preserve their current roles
```

## 💡 BEST PRACTICES FROM INDUSTRY

### 1. Slack Model
- Simple registration
- Create workspace = become admin
- Invite team = assign roles

### 2. GitHub Model
- Register as user
- Create organization = become owner
- Invite collaborators = assign permissions

### 3. Zendesk Model
- Register as agent or customer (separate flows)
- Agents need invitation
- Customers self-register

## 🎯 RECOMMENDATION SUMMARY

**For FieldRino, implement Option A (Simplified Registration):**

1. ✅ Remove role from registration
2. ✅ Add onboarding flow after email verification
3. ✅ Implement tenant-specific roles
4. ✅ Add invitation system for team members
5. ✅ Separate customer registration flow

**Benefits:**
- ✅ Secure (no self-assigned admin)
- ✅ Industry standard
- ✅ Better UX
- ✅ Multi-tenant ready
- ✅ Scalable

**Timeline:**
- Phase 1 (Quick Fix): 1-2 days
- Phase 2 (Full Implementation): 1-2 weeks

---

**Questions or concerns?** Let's discuss the best approach for your specific use case.
