# FieldRino AWS Deployment Guide - Complete Walkthrough

This is a step-by-step guide to deploy FieldRino on AWS following the $40/month architecture.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Setup](#pre-deployment-setup)
3. [Infrastructure Deployment](#infrastructure-deployment)
4. [Application Setup](#application-setup)
5. [SSL Configuration](#ssl-configuration)
6. [Verification](#verification)
7. [Post-Deployment](#post-deployment)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

Install these on your local machine:

```bash
# Terraform
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# AWS CLI
pip install awscli
# or brew install awscli

# Git
brew install git  # macOS
# or apt-get install git  # Linux
```

### AWS Account Setup

1. **Create AWS Account**: https://aws.amazon.com/
2. **Create IAM User** with these permissions:
   - AmazonEC2FullAccess
   - AmazonRDSFullAccess
   - AmazonElastiCacheFullAccess
   - AmazonS3FullAccess
   - CloudFrontFullAccess
   - Route53FullAccess
   - IAMFullAccess
   - CloudWatchFullAccess

3. **Configure AWS CLI**:
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: ap-south-1
# Default output format: json
```

4. **Verify credentials**:
```bash
aws sts get-caller-identity
```

## Pre-Deployment Setup

### 1. Domain Name

You need a registered domain name. If you don't have one:
- Register at Namecheap, GoDaddy, or AWS Route 53
- Cost: ~$10-15/year

### 2. Create EC2 Key Pair

```bash
# In AWS Console:
# 1. Go to EC2 > Key Pairs
# 2. Click "Create key pair"
# 3. Name: fieldrino-prod
# 4. Type: RSA
# 5. Format: .pem
# 6. Download and save to ~/.ssh/

# Set permissions
chmod 400 ~/.ssh/fieldrino-prod.pem
```

### 3. Generate Secrets

```bash
# Django secret key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Database password (or use a password generator)
openssl rand -base64 32
```

### 4. Get Stripe Keys (Optional)

If using billing features:
1. Create account at https://stripe.com
2. Get API keys from Dashboard > Developers > API keys
3. Note down:
   - Secret key (sk_live_...)
   - Publishable key (pk_live_...)
   - Webhook secret (whsec_...)

### 5. Email Configuration

Choose one:

**Option A: Gmail SMTP**
1. Enable 2FA on your Gmail account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use: smtp.gmail.com:587

**Option B: AWS SES**
1. Verify your domain in SES
2. Request production access (if needed)
3. Create SMTP credentials

## Infrastructure Deployment

### Step 1: Configure Terraform

```bash
# Navigate to terraform directory
cd aws/terraform

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Fill in terraform.tfvars:**

```hcl
# AWS Configuration
aws_region = "ap-south-1"
environment = "production"

# Domain
domain_name = "yourdomain.com"  # CHANGE THIS

# Database
db_name     = "fieldrino_db"
db_username = "fieldrino_admin"
db_password = "YOUR_STRONG_PASSWORD_HERE"  # CHANGE THIS

# Django
django_secret_key = "YOUR_DJANGO_SECRET_KEY_HERE"  # CHANGE THIS

# Stripe (optional)
stripe_secret_key      = "sk_live_..."
stripe_publishable_key = "pk_live_..."
stripe_webhook_secret  = "whsec_..."

# Email
email_host_user     = "your-email@gmail.com"  # CHANGE THIS
email_host_password = "your-app-password"     # CHANGE THIS

# SSH
ssh_key_name     = "fieldrino-prod"
allowed_ssh_cidr = "YOUR_IP_ADDRESS/32"  # CHANGE THIS
```

**Get your IP address:**
```bash
curl ifconfig.me
# Use the output with /32, e.g., "203.0.113.1/32"
```

### Step 2: Initialize Terraform

```bash
terraform init
```

Expected output:
```
Terraform has been successfully initialized!
```

### Step 3: Plan Infrastructure

```bash
terraform plan -out=tfplan
```

Review the output carefully. You should see:
- 1 VPC
- 4 Subnets
- 1 EC2 instance
- 1 RDS instance
- 1 ElastiCache cluster
- 2 S3 buckets
- 1 CloudFront distribution
- Security groups
- IAM roles
- CloudWatch alarms
- SNS topic

### Step 4: Deploy Infrastructure

```bash
terraform apply tfplan
```

This will take 10-15 minutes. Grab a coffee! ☕

When complete, you'll see outputs:
```
Outputs:

ec2_public_ip = "203.0.113.1"
rds_endpoint = "fieldrino-db.xxxxx.ap-south-1.rds.amazonaws.com:5432"
redis_endpoint = "fieldrino-redis.xxxxx.cache.amazonaws.com:6379"
...
```

**Save these outputs!** You'll need them.

```bash
terraform output > ../outputs.txt
```

### Step 5: Configure DNS

If using Route 53:
- DNS records are automatically created
- Wait 5-10 minutes for propagation

If using external DNS provider:
1. Get EC2 IP: `terraform output ec2_public_ip`
2. Add these DNS records at your registrar:
   - A record: `yourdomain.com` → EC2 IP
   - A record: `*.yourdomain.com` → EC2 IP
   - A record: `api.yourdomain.com` → EC2 IP

**Verify DNS:**
```bash
dig yourdomain.com
dig test.yourdomain.com
```

## Application Setup

### Step 1: SSH into EC2

```bash
# Get SSH command
cd aws/terraform
terraform output ssh_command

# SSH into server
ssh -i ~/.ssh/fieldrino-prod.pem ubuntu@<EC2_IP>
```

### Step 2: Verify User Data Script

```bash
# Check if user data script completed
sudo tail -100 /var/log/cloud-init-output.log

# Verify directories exist
ls -la /opt/fieldrino/
ls -la /var/log/fieldrino/
```

### Step 3: Clone Application

```bash
# Switch to fieldrino user
sudo su - fieldrino

# Clone your repository
cd /opt/fieldrino
git clone https://github.com/yourusername/fieldrino.git app

# Or if using private repo with deploy key:
# git clone git@github.com:yourusername/fieldrino.git app
```

### Step 4: Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv /opt/fieldrino/venv

# Activate it
source /opt/fieldrino/venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
cd /opt/fieldrino/app
pip install -r requirements.txt

# Install additional packages for AWS
pip install django-storages boto3 django-redis
```

### Step 5: Verify Environment Variables

```bash
# Check .env file (created by user data script)
cat /opt/fieldrino/.env

# Verify all values are correct
# If needed, edit:
nano /opt/fieldrino/.env
```

### Step 6: Run Migrations

```bash
# Test database connection
python manage.py dbshell
# Type \q to exit

# Run migrations
python manage.py migrate

# Create public tenant (if using django-tenants)
python manage.py create_public_tenant

# Create superuser
python manage.py createsuperuser
# Enter username, email, password
```

### Step 7: Collect Static Files

```bash
# This uploads to S3
python manage.py collectstatic --noinput

# Verify files in S3
aws s3 ls s3://fieldrino-static-production/
```

### Step 8: Test Application

```bash
# Test Django
python manage.py check --deploy

# Test Celery connection
python manage.py shell
>>> from celery import current_app
>>> current_app.control.inspect().active()
>>> exit()
```

## SSL Configuration

### Step 1: Wait for DNS Propagation

```bash
# Verify DNS is working
dig yourdomain.com
dig www.yourdomain.com

# Should return your EC2 IP
```

### Step 2: Obtain SSL Certificate

```bash
# Exit from fieldrino user
exit

# Run Certbot
sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com

# Follow prompts:
# - Enter email address
# - Agree to terms
# - Choose whether to redirect HTTP to HTTPS (recommended: yes)
```

**Note**: Wildcard certificates require DNS validation. Certbot will provide instructions.

### Step 3: Verify SSL

```bash
# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Check certificate
sudo certbot certificates
```

## Start Services

### Step 1: Start Supervisor Services

```bash
# Reload Supervisor configuration
sudo supervisorctl reread
sudo supervisorctl update

# Start all services
sudo supervisorctl start all

# Check status
sudo supervisorctl status
```

Expected output:
```
celery-beat                      RUNNING   pid 1234, uptime 0:00:05
celery-worker                    RUNNING   pid 1235, uptime 0:00:05
gunicorn                         RUNNING   pid 1236, uptime 0:00:05
```

### Step 2: Check Logs

```bash
# Gunicorn logs
sudo tail -f /var/log/gunicorn/error.log

# Celery logs
sudo tail -f /var/log/celery/worker.log

# Nginx logs
sudo tail -f /var/log/nginx/fieldrino-error.log
```

## Verification

### 1. Health Check

```bash
# From EC2
curl http://localhost:8000/api/health/

# From your machine
curl https://yourdomain.com/api/health/
```

Expected: `{"status": "healthy"}`

### 2. API Documentation

Visit: `https://yourdomain.com/api/docs/`

You should see the Swagger UI.

### 3. Admin Panel

Visit: `https://yourdomain.com/admin/`

Login with your superuser credentials.

### 4. Test Multi-Tenancy

1. Create a test tenant in admin
2. Visit: `https://tenant1.yourdomain.com/`
3. Should work with SSL

### 5. Test File Upload

1. Upload a file through admin or API
2. Verify it's in S3:
```bash
aws s3 ls s3://fieldrino-media-production/
```

### 6. Test Email

```bash
# Django shell
python manage.py shell

# Send test email
from django.core.mail import send_mail
send_mail(
    'Test Email',
    'This is a test.',
    'noreply@yourdomain.com',
    ['your-email@example.com'],
)
```

### 7. Test Celery

```bash
# Django shell
python manage.py shell

# Queue a test task
from apps.billing.tasks import check_subscription_status
result = check_subscription_status.delay()
print(result.id)
```

Check Celery logs to see it processed.

## Post-Deployment

### 1. Confirm SNS Subscription

Check your email for SNS subscription confirmation and click the link.

### 2. Set Up Monitoring

```bash
# Verify CloudWatch Agent is running
sudo systemctl status amazon-cloudwatch-agent

# Check metrics are being sent
aws cloudwatch list-metrics --namespace FieldRino/EC2
```

### 3. Create Initial Backup

```bash
# Create RDS snapshot
aws rds create-db-snapshot \
  --db-instance-identifier fieldrino-db \
  --db-snapshot-identifier initial-backup-$(date +%Y%m%d)
```

### 4. Document Everything

Save these in a secure location:
- EC2 IP address
- RDS endpoint
- Redis endpoint
- Database credentials
- Django secret key
- Stripe keys
- SSH key location

### 5. Set Up Uptime Monitoring

Use a service like:
- UptimeRobot (free)
- Pingdom
- StatusCake

Monitor: `https://yourdomain.com/api/health/`

### 6. Configure Sentry (Optional)

```bash
# Install Sentry SDK
pip install sentry-sdk

# Add to .env
echo "SENTRY_DSN=your-sentry-dsn" >> /opt/fieldrino/.env

# Restart services
sudo supervisorctl restart all
```

## Troubleshooting

### Services Won't Start

```bash
# Check Supervisor logs
sudo supervisorctl tail gunicorn stderr
sudo supervisorctl tail celery-worker stderr

# Check if ports are in use
sudo netstat -tulpn | grep :8000

# Restart services
sudo supervisorctl restart all
```

### Database Connection Error

```bash
# Test connection
psql -h <RDS_ENDPOINT> -U fieldrino_admin -d fieldrino_db

# Check security group
aws ec2 describe-security-groups --group-ids <RDS_SG_ID>

# Verify .env has correct DATABASE_URL
cat /opt/fieldrino/.env | grep DATABASE_URL
```

### SSL Certificate Issues

```bash
# Check DNS
dig yourdomain.com

# Test certificate
openssl s_client -connect yourdomain.com:443

# Renew certificate
sudo certbot renew --dry-run

# Check Nginx config
sudo nginx -t
```

### High CPU/Memory

```bash
# Check processes
top
htop

# Check Gunicorn workers
ps aux | grep gunicorn

# Consider upgrading instance
# Update terraform.tfvars:
# ec2_instance_type = "t3a.medium"
# Then: terraform apply
```

### Can't Access Application

```bash
# Check Nginx
sudo systemctl status nginx
sudo nginx -t

# Check Gunicorn
sudo supervisorctl status gunicorn

# Check firewall
sudo ufw status

# Check security group
aws ec2 describe-security-groups --group-ids <EC2_SG_ID>
```

## Next Steps

1. **Purchase Reserved Instances** (after 2-3 months)
   - Save ~$13/month
   - Go to EC2/RDS/ElastiCache console

2. **Set Up CI/CD**
   - GitHub Actions
   - Automated deployments
   - Automated tests

3. **Configure Backups**
   - Automated RDS snapshots (already enabled)
   - Application file backups
   - Configuration backups

4. **Performance Optimization**
   - Enable query caching
   - Optimize database queries
   - Add CDN for API responses

5. **Security Hardening**
   - Regular security updates
   - Penetration testing
   - Security audit

## Support

If you encounter issues:

1. Check logs: `/var/log/fieldrino/`, `/var/log/gunicorn/`, `/var/log/celery/`
2. Review CloudWatch metrics and alarms
3. Check AWS Service Health Dashboard
4. Consult documentation in `aws/` directory

---

**Congratulations! Your FieldRino application is now running on AWS! 🎉**
