# FieldRino AWS Deployment Guide

Complete AWS infrastructure setup for FieldRino following the $40/month budget architecture.

## 📋 Architecture Overview

This deployment creates:
- **EC2 t3a.small** - Application server (Django + Gunicorn + Celery + Nginx)
- **RDS PostgreSQL db.t3.micro** - Database with multi-tenant support
- **ElastiCache Redis cache.t3.micro** - Caching and Celery task queue
- **S3 + CloudFront** - Media and static file storage with CDN
- **Route 53** - DNS with wildcard subdomain support
- **CloudWatch** - Monitoring and alerts
- **SNS** - Email/SMS alerts

**Estimated Cost**: ~$40/month (on-demand) or ~$27/month (1-year reserved instances)

## 🚀 Quick Start

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured (`aws configure`)
3. **Terraform** >= 1.0 installed
4. **Domain name** registered and ready
5. **EC2 Key Pair** created in AWS console
6. **Git repository** for your application code

### Step 1: Install Required Tools

```bash
# Install Terraform (macOS)
brew install terraform

# Install Terraform (Linux)
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure
```

### Step 2: Configure Variables

```bash
cd aws/terraform

# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Required values in terraform.tfvars:**

```hcl
domain_name        = "yourdomain.com"
db_password        = "generate-strong-password"
django_secret_key  = "generate-with-django"
ssh_key_name       = "your-ec2-key-pair"
allowed_ssh_cidr   = "YOUR_IP/32"

# Optional: Stripe keys
stripe_secret_key      = "sk_live_..."
stripe_publishable_key = "pk_live_..."

# Optional: Email credentials
email_host_user     = "your-email@domain.com"
email_host_password = "your-password"
```

**Generate Django secret key:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Step 3: Create EC2 Key Pair

```bash
# In AWS Console:
# 1. Go to EC2 > Key Pairs
# 2. Click "Create key pair"
# 3. Name: fieldrino-prod
# 4. Type: RSA
# 5. Format: .pem
# 6. Download and save to ~/.ssh/fieldrino-prod.pem
# 7. Set permissions: chmod 400 ~/.ssh/fieldrino-prod.pem
```

### Step 4: Set Up Route 53 (if not already done)

```bash
# Option 1: Create hosted zone via AWS Console
# Go to Route 53 > Hosted zones > Create hosted zone

# Option 2: Use Terraform (uncomment in route53.tf)
# Then update your domain registrar with the NS records
```

### Step 5: Deploy Infrastructure

```bash
# Run the automated setup script
cd aws
./scripts/setup.sh

# Or manually:
cd terraform
terraform init
terraform plan
terraform apply
```

This will create all AWS resources (~10-15 minutes).

### Step 6: Initial Server Setup

After Terraform completes, SSH into your EC2 instance:

```bash
# Get SSH command from Terraform output
terraform output ssh_command

# SSH into server
ssh -i ~/.ssh/fieldrino-prod.pem ubuntu@<EC2_IP>
```

**On the EC2 server:**

```bash
# 1. Clone your application
cd /opt/fieldrino
sudo -u fieldrino git clone https://github.com/yourusername/fieldrino.git app

# 2. Create virtual environment
sudo -u fieldrino python3.11 -m venv /opt/fieldrino/venv

# 3. Install dependencies
sudo -u fieldrino /opt/fieldrino/venv/bin/pip install -r /opt/fieldrino/app/requirements.txt

# 4. Install django-storages for S3
sudo -u fieldrino /opt/fieldrino/venv/bin/pip install django-storages boto3

# 5. Run migrations
sudo -u fieldrino /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py migrate

# 6. Create superuser
sudo -u fieldrino /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py createsuperuser

# 7. Collect static files (uploads to S3)
sudo -u fieldrino /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py collectstatic --noinput

# 8. Set up SSL certificate with Certbot
sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com

# 9. Start all services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all

# 10. Check service status
sudo supervisorctl status
```

### Step 7: Verify Deployment

```bash
# Check health endpoint
curl https://yourdomain.com/api/health/

# Check Gunicorn logs
sudo tail -f /var/log/gunicorn/error.log

# Check Celery logs
sudo tail -f /var/log/celery/worker.log

# Check Nginx logs
sudo tail -f /var/log/nginx/fieldrino-error.log
```

## 📦 What Gets Created

### Networking
- VPC with public and private subnets across 2 AZs
- Internet Gateway
- Route tables
- Security groups (EC2, RDS, ElastiCache)

### Compute
- EC2 t3a.small instance with Elastic IP
- IAM role with S3, SES, and CloudWatch permissions
- CloudWatch alarms for CPU, memory, disk

### Database
- RDS PostgreSQL db.t3.micro (single-AZ)
- Automated backups (7-day retention)
- Performance Insights enabled
- CloudWatch alarms for connections, CPU, storage

### Cache
- ElastiCache Redis cache.t3.micro
- Automated snapshots
- CloudWatch alarms for CPU, memory, evictions

### Storage & CDN
- S3 bucket for media files (private)
- S3 bucket for static files (public via CloudFront)
- CloudFront distribution with OAI
- Lifecycle policies for cost optimization

### DNS
- Route 53 A records for main domain
- Wildcard A record for tenant subdomains
- CNAME for CDN subdomain

### Monitoring
- SNS topic for alerts
- CloudWatch alarms for all services
- CloudWatch Logs for application logs
- CloudWatch Agent for custom metrics

## 🔄 Deployment Workflow

### Regular Deployments

```bash
# From your local machine
cd aws
./scripts/deploy.sh
```

This script will:
1. Create RDS snapshot (safety backup)
2. SSH into EC2
3. Pull latest code
4. Install dependencies
5. Run migrations
6. Collect static files
7. Restart services gracefully
8. Verify health check

### Manual Deployment

```bash
# SSH into EC2
ssh -i ~/.ssh/fieldrino-prod.pem ubuntu@<EC2_IP>

# Run deployment script
sudo -u fieldrino /opt/fieldrino/deploy.sh
```

## 📊 Monitoring & Alerts

### CloudWatch Alarms

All alarms send notifications to your email via SNS:

- **EC2 CPU > 80%** - Consider upgrading instance
- **EC2 Status Check Failed** - Auto-recovery triggered
- **RDS CPU > 80%** - Database under load
- **RDS Storage < 2GB** - Need more storage
- **RDS Connections > 80** - Connection pool issue
- **Redis CPU > 75%** - Cache under load
- **Redis Memory > 80%** - Memory pressure
- **Redis Evictions > 100** - Cache too small

### View Logs

```bash
# Application logs
sudo tail -f /var/log/gunicorn/error.log

# Celery worker logs
sudo tail -f /var/log/celery/worker.log

# Celery beat logs
sudo tail -f /var/log/celery/beat.log

# Nginx access logs
sudo tail -f /var/log/nginx/fieldrino-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/fieldrino-error.log
```

### CloudWatch Logs

Logs are automatically sent to CloudWatch:
- `/fieldrino/gunicorn` - Application logs
- `/fieldrino/celery` - Background task logs
- `/fieldrino/nginx` - Web server logs

## 💰 Cost Optimization

### Use Reserved Instances (Save ~$13/month)

After confirming everything works, purchase 1-year reserved instances:

```bash
# In AWS Console:
# 1. EC2 > Reserved Instances > Purchase Reserved Instances
#    - Instance type: t3a.small
#    - Term: 1 year
#    - Payment: No upfront
#
# 2. RDS > Reserved Instances > Purchase Reserved DB Instance
#    - Instance class: db.t3.micro
#    - Term: 1 year
#    - Payment: No upfront
#
# 3. ElastiCache > Reserved Nodes > Purchase Reserved Node
#    - Node type: cache.t3.micro
#    - Term: 1 year
#    - Payment: No upfront
```

**Savings**: ~$40/month → ~$27/month

### S3 Lifecycle Policies

Already configured to:
- Delete old file versions after 30 days
- Move files to Infrequent Access after 90 days

### CloudFront Optimization

- Using PriceClass_100 (cheapest)
- Compression enabled
- Long cache TTLs

## 🔒 Security Best Practices

### Implemented
✅ All data encrypted at rest (EBS, RDS, S3)
✅ TLS 1.2+ for all connections
✅ Security groups restrict access
✅ IAM roles (no hardcoded credentials)
✅ Private subnets for database and cache
✅ RDS deletion protection enabled
✅ Automated backups enabled
✅ CloudWatch monitoring and alerts

### Recommended
- [ ] Restrict SSH access to your IP only (update `allowed_ssh_cidr`)
- [ ] Enable MFA for AWS root account
- [ ] Set up AWS CloudTrail for audit logs
- [ ] Enable AWS GuardDuty for threat detection
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`
- [ ] Rotate database passwords regularly
- [ ] Review IAM permissions quarterly

## 🔧 Troubleshooting

### Services Not Starting

```bash
# Check Supervisor status
sudo supervisorctl status

# Restart all services
sudo supervisorctl restart all

# Check for errors
sudo supervisorctl tail gunicorn stderr
sudo supervisorctl tail celery-worker stderr
```

### Database Connection Issues

```bash
# Test database connection
psql -h <RDS_ENDPOINT> -U fieldrino_admin -d fieldrino_db

# Check security group allows EC2 -> RDS
# Check .env file has correct DATABASE_URL
```

### SSL Certificate Issues

```bash
# Renew certificate
sudo certbot renew

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### High CPU Usage

```bash
# Check processes
top

# Check Gunicorn workers
ps aux | grep gunicorn

# Check Celery workers
ps aux | grep celery

# Consider upgrading to t3a.medium
```

## 📈 Scaling Up

When you need more capacity:

### Vertical Scaling (Easier)

```bash
# Update terraform.tfvars
ec2_instance_type = "t3a.medium"  # 4 GB RAM
rds_instance_class = "db.t3.small"  # 2 GB RAM

# Apply changes
terraform apply
```

### Horizontal Scaling (Better)

For true high-availability (~$90/month):
- Add Application Load Balancer
- Add second EC2 instance
- Enable RDS Multi-AZ
- Separate Celery to its own instance

See `aws_deployment_guide.html` Section 13 for details.

## 🆘 Support

### Terraform Issues
- Check `terraform.log` for errors
- Verify AWS credentials: `aws sts get-caller-identity`
- Ensure sufficient IAM permissions

### Application Issues
- Check CloudWatch Logs
- Review Sentry errors (if configured)
- SSH into EC2 and check logs

### AWS Issues
- Check AWS Service Health Dashboard
- Review CloudWatch alarms
- Check billing dashboard for unexpected costs

## 📚 Additional Resources

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Gunicorn Deployment](https://docs.gunicorn.org/en/stable/deploy.html)
- [Celery Production](https://docs.celeryproject.org/en/stable/userguide/deployment.html)

## 📝 Maintenance Checklist

### Daily
- [ ] Check CloudWatch alarms
- [ ] Monitor application errors in Sentry

### Weekly
- [ ] Review CloudWatch metrics
- [ ] Check disk space usage
- [ ] Review application logs

### Monthly
- [ ] Review AWS bill
- [ ] Update system packages
- [ ] Review security groups
- [ ] Test backup restoration

### Quarterly
- [ ] Update Python dependencies
- [ ] Review and rotate secrets
- [ ] Performance optimization review
- [ ] Security audit

---

**Need Help?** Open an issue or contact the DevOps team.
