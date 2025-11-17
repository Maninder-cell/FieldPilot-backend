# FieldRino - Security Documentation

## Security Overview

FieldRino implements enterprise-grade security measures to protect tenant data, ensure compliance, and prevent unauthorized access.

## Authentication & Authorization

### JWT Authentication

```python
# Token Configuration
ACCESS_TOKEN_LIFETIME = 15 minutes
REFRESH_TOKEN_LIFETIME = 7 days
ROTATE_REFRESH_TOKENS = True
BLACKLIST_AFTER_ROTATION = True
```

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character
- Cannot be common passwords
- Cannot be similar to username/email

```python
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
```

### Two-Factor Authentication (2FA)

```python
# Enable 2FA for user
POST /api/v1/auth/2fa/enable/
{
  "method": "totp"  # or "sms"
}

# Verify 2FA code
POST /api/v1/auth/2fa/verify/
{
  "code": "123456"
}
```

### Single Sign-On (SSO)

Supported protocols:
- SAML 2.0
- OAuth 2.0 (Google, Microsoft, Okta)

```python
# SSO Configuration (Enterprise plan)
SAML_ENABLED = True
SAML_IDP_METADATA_URL = "https://idp.example.com/metadata"
```

## Data Encryption

### At Rest

- **Database**: AES-256 encryption for RDS
- **File Storage**: S3 server-side encryption (SSE-S3)
- **Backups**: Encrypted snapshots
- **Sensitive Fields**: Additional field-level encryption

```python
from django_cryptography.fields import encrypt

class User(models.Model):
    ssn = encrypt(models.CharField(max_length=11))  # Field-level encryption
```

### In Transit

- **TLS 1.3** for all API communications
- **HTTPS only** - HTTP redirects to HTTPS
- **Certificate pinning** for mobile apps
- **HSTS** (HTTP Strict Transport Security)

```python
# Django Settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

## Multi-Tenant Security

### Schema Isolation

Each tenant operates in a dedicated PostgreSQL schema:

```sql
-- Tenant 1 data
SET search_path TO tenant_acme_corp;
SELECT * FROM equipment;  -- Only sees Acme Corp data

-- Tenant 2 data
SET search_path TO tenant_xyz_services;
SELECT * FROM equipment;  -- Only sees XYZ Services data
```

### Middleware Protection

```python
class TenantMiddleware:
    def __call__(self, request):
        # Extract tenant from domain
        tenant = get_tenant_from_request(request)
        
        # Set database schema
        connection.set_schema(tenant.schema_name)
        
        # Prevent cross-tenant access
        request.tenant = tenant
```

### Row-Level Security (Additional Layer)

```sql
-- Enable RLS on sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

## API Security

### Rate Limiting

```python
# Rate limits by plan
RATE_LIMITS = {
    'starter': '1000/hour',
    'professional': '5000/hour',
    'enterprise': '20000/hour'
}

# Throttle classes
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'apps.core.throttling.TenantRateThrottle',
    ],
}
```

### CORS Configuration

```python
CORS_ALLOWED_ORIGINS = [
    "https://fieldrino.com",
    "https://*.fieldrino.com",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
```

### API Key Management

```python
# Generate API key
POST /api/v1/api-keys/
{
  "name": "Integration Key",
  "permissions": ["read:equipment", "write:tasks"],
  "expires_at": "2026-01-01T00:00:00Z"
}

# Rotate API key
POST /api/v1/api-keys/{key_id}/rotate/

# Revoke API key
DELETE /api/v1/api-keys/{key_id}/
```

## Input Validation & Sanitization

### SQL Injection Prevention

```python
# Always use Django ORM (parameterized queries)
Equipment.objects.filter(name=user_input)  # Safe

# Never use raw SQL with user input
# BAD: cursor.execute(f"SELECT * FROM equipment WHERE name = '{user_input}'")
```

### XSS Prevention

```python
# Django templates auto-escape by default
{{ equipment.name }}  # Automatically escaped

# React also escapes by default
<div>{equipment.name}</div>  # Safe
```

### CSRF Protection

```python
# Django CSRF middleware (enabled by default)
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
]

# CSRF token in forms
{% csrf_token %}

# CSRF token in AJAX requests
headers: {
    'X-CSRFToken': getCookie('csrftoken')
}
```

## File Upload Security

### Validation

```python
# Allowed file types
ALLOWED_UPLOAD_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif',  # Images
    '.pdf', '.doc', '.docx',  # Documents
    '.xls', '.xlsx', '.csv'  # Spreadsheets
]

# Max file size
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# Virus scanning (ClamAV)
def scan_file(file):
    cd = clamd.ClamdUnixSocket()
    result = cd.scan_stream(file.read())
    return result['stream'][0] == 'OK'
```

### Storage Security

```python
# S3 bucket policy - private by default
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::fieldrino-files/*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalAccount": "ACCOUNT_ID"
        }
      }
    }
  ]
}

# Generate signed URLs for temporary access
def get_signed_url(file_key):
    s3_client = boto3.client('s3')
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': 'fieldrino-files', 'Key': file_key},
        ExpiresIn=3600  # 1 hour
    )
    return url
```

## Audit Logging

### Activity Tracking

```python
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.UUIDField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    changes = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

# Log all sensitive operations
@audit_log(action='equipment.delete')
def delete_equipment(request, equipment_id):
    equipment = Equipment.objects.get(id=equipment_id)
    equipment.delete()
```

### Retention Policy

- Audit logs retained for 1 year (Starter/Professional)
- Audit logs retained for 7 years (Enterprise)
- Archived to S3 Glacier after 90 days

## Vulnerability Management

### Dependency Scanning

```bash
# Python dependencies
pip install safety
safety check

# Node.js dependencies
npm audit
npm audit fix

# Automated scanning in CI/CD
- name: Security Scan
  run: |
    pip install safety
    safety check --json
```

### Regular Updates

```bash
# Update Python packages
pip list --outdated
pip install --upgrade package-name

# Update Node.js packages
npm outdated
npm update

# Automated updates with Dependabot
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
```

### Penetration Testing

- Annual third-party penetration testing
- Quarterly internal security assessments
- Bug bounty program (post-launch)

## Incident Response

### Security Incident Procedure

1. **Detection**: Monitor logs, alerts, user reports
2. **Containment**: Isolate affected systems
3. **Investigation**: Determine scope and impact
4. **Eradication**: Remove threat, patch vulnerabilities
5. **Recovery**: Restore services, verify integrity
6. **Post-Incident**: Document lessons learned, update procedures

### Breach Notification

- Notify affected users within 72 hours
- Report to authorities as required (GDPR, CCPA)
- Provide remediation steps
- Offer credit monitoring if PII compromised

## Compliance

### GDPR Compliance

```python
# Right to access
GET /api/v1/users/me/data-export/

# Right to erasure
DELETE /api/v1/users/me/

# Right to data portability
GET /api/v1/users/me/data-export/?format=json

# Consent management
POST /api/v1/users/me/consent/
{
  "marketing_emails": true,
  "analytics": true
}
```

### CCPA Compliance

- Do Not Sell My Personal Information
- Right to know what data is collected
- Right to delete personal information
- Right to opt-out of data sales

### SOC 2 Type II (Roadmap)

- Security controls documentation
- Annual audit by certified auditor
- Continuous monitoring and reporting

## Security Headers

```python
# Django Security Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.stripe.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
```

## Database Security

### Connection Security

```python
# SSL/TLS for database connections
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'sslmode': 'require',
            'sslrootcert': '/path/to/ca-cert.pem',
        }
    }
}
```

### Backup Encryption

```bash
# Encrypted backups
pg_dump fieldrino_db | \
  openssl enc -aes-256-cbc -salt -out backup.sql.enc

# Restore encrypted backup
openssl enc -d -aes-256-cbc -in backup.sql.enc | \
  psql fieldrino_db
```

### Access Control

```sql
-- Principle of least privilege
CREATE ROLE app_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE fieldrino_db TO app_user;
GRANT USAGE ON SCHEMA tenant_* TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tenant_* TO app_user;

-- Read-only user for analytics
CREATE ROLE analytics_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE fieldrino_db TO analytics_user;
GRANT SELECT ON ALL TABLES IN SCHEMA tenant_* TO analytics_user;
```

## Secrets Management

### AWS Secrets Manager

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
db_credentials = get_secret('fieldrino/prod/database')
DATABASE_URL = db_credentials['connection_string']
```

### Environment Variables

```bash
# Never commit secrets to git
# Use .env files (gitignored)
# Use environment variables in production

# Rotate secrets regularly
# Database passwords: Every 90 days
# API keys: Every 180 days
# JWT secret: Every year
```

## Monitoring & Alerting

### Security Monitoring

```python
# Failed login attempts
if failed_login_count > 5:
    send_alert(f"Multiple failed login attempts for {email}")
    lock_account(email, duration=30)  # 30 minutes

# Unusual activity detection
if login_from_new_location:
    send_verification_email(user)
    require_2fa_verification()

# API abuse detection
if request_rate > threshold:
    block_ip(ip_address, duration=3600)  # 1 hour
```

### Security Alerts

- Failed login attempts (>5 in 10 minutes)
- Unusual API usage patterns
- Database connection failures
- File upload anomalies
- Privilege escalation attempts
- Data export requests
- Account deletions

## Security Best Practices

### For Developers

1. Never commit secrets to version control
2. Use parameterized queries (ORM)
3. Validate and sanitize all user input
4. Use HTTPS for all communications
5. Implement proper error handling (don't leak info)
6. Keep dependencies up to date
7. Follow principle of least privilege
8. Write security tests
9. Use security linters (bandit, eslint-plugin-security)
10. Review code for security issues

### For Users

1. Use strong, unique passwords
2. Enable two-factor authentication
3. Don't share account credentials
4. Review audit logs regularly
5. Report suspicious activity immediately
6. Keep software up to date
7. Use secure networks (avoid public WiFi)
8. Be cautious of phishing attempts

## Security Contacts

- **Security Issues**: security@fieldrino.com
- **Bug Bounty**: bugbounty@fieldrino.com
- **Privacy Concerns**: privacy@fieldrino.com

## Security Disclosure Policy

If you discover a security vulnerability:

1. **Do not** publicly disclose the issue
2. Email security@fieldrino.com with details
3. Allow 90 days for remediation
4. We will acknowledge receipt within 24 hours
5. We will provide updates on remediation progress
6. We will credit you in our security hall of fame (if desired)

## Security Roadmap

### Q1 2026
- [ ] SOC 2 Type II certification
- [ ] Bug bounty program launch
- [ ] Advanced threat detection (ML-based)

### Q2 2026
- [ ] ISO 27001 certification
- [ ] HIPAA compliance (for healthcare customers)
- [ ] Enhanced DLP (Data Loss Prevention)

### Q3 2026
- [ ] Zero-trust architecture implementation
- [ ] Advanced encryption (homomorphic encryption research)
- [ ] Quantum-resistant cryptography evaluation
