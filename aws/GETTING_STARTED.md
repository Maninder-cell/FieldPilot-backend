# Getting Started with FieldRino AWS Deployment

Quick start guide to deploy FieldRino on AWS in under 30 minutes.

## What You'll Get

- **EC2 t3a.small** - Application server running Django, Celery, and Nginx
- **RDS PostgreSQL** - Managed database with automated backups
- **ElastiCache Redis** - Caching and task queue
- **S3 + CloudFront** - File storage and CDN
- **Route 53** - DNS with wildcard subdomain support
- **CloudWatch** - Monitoring and alerts
- **Cost**: ~$40/month (or ~$27/month with reserved instances)

## Prerequisites Checklist

- [ ] AWS account with billing enabled
- [ ] Domain name registered
- [ ] AWS CLI installed and configured
- [ ] Terraform installed (>= 1.0)
- [ ] SSH client available
- [ ] 30 minutes of your time

## Quick Start (5 Steps)

### 1. Install Tools (5 minutes)

```bash
# macOS
brew install terraform awscli

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
pip install awscli

# Configure AWS
aws configure
```

### 2. Prepare Secrets (5 minutes)

```bash
# Create EC2 key pair in AWS Console
# EC2 > Key Pairs > Create key pair
# Name: fieldrino-prod, Type: RSA, Format: .pem
# Download to ~/.ssh/ and chmod 400

# Generate Django secret key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Generate database password
openssl rand -base64 32
```

### 3. Configure Terraform (5 minutes)

```bash
cd aws/terraform
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```

**Minimum required changes:**
- `domain_name` - Your domain
- `db_password` - Strong password
- `django_secret_key` - Generated key
- `ssh_key_name` - "fieldrino-prod"
- `allowed_ssh_cidr` - Your IP/32
- `email_host_user` - Your email
- `email_host_password` - SMTP password

### 4. Deploy Infrastructure (10 minutes)

```bash
# Initialize and deploy
terraform init
terraform plan
terraform apply

# Save outputs
terraform output > ../outputs.txt
```

### 5. Set Up Application (10 minutes)

```bash
# SSH into EC2
ssh -i ~/.ssh/fieldrino-prod.pem ubuntu@<EC2_IP>

# Clone your app
sudo su - fieldrino
cd /opt/fieldrino
git clone <your-repo-url> app

# Set up Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
pip install django-storages boto3 django-redis

# Run migrations
cd app
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput

# Exit and start services
exit
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all

# Set up SSL (requires DNS to be configured)
sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com
```

## Verify Deployment

```bash
# Check health
curl https://yourdomain.com/api/health/

# Check services
sudo supervisorctl status

# View logs
sudo tail -f /var/log/gunicorn/error.log
```

## What's Next?

1. **Configure DNS** - Point your domain to EC2 IP
2. **Set up monitoring** - Confirm SNS email subscription
3. **Create backups** - Take initial RDS snapshot
4. **Test thoroughly** - Verify all features work
5. **Go live!** 🚀

## Common Issues

### DNS not resolving
- Wait 5-10 minutes for propagation
- Verify with: `dig yourdomain.com`

### SSL certificate fails
- Ensure DNS is configured first
- Use DNS validation for wildcard certs

### Services won't start
- Check logs: `sudo supervisorctl tail gunicorn stderr`
- Verify .env file: `cat /opt/fieldrino/.env`

### Can't connect to database
- Check security group allows EC2 → RDS
- Verify DATABASE_URL in .env

## Documentation

- **[Complete Deployment Guide](DEPLOYMENT_GUIDE.md)** - Step-by-step walkthrough
- **[Setup Checklist](SETUP_CHECKLIST.md)** - Comprehensive checklist
- **[Quick Reference](QUICK_REFERENCE.md)** - Common commands
- **[Cost Breakdown](COST_BREAKDOWN.md)** - Detailed cost analysis
- **[README](README.md)** - Full documentation

## Support

Need help? Check:
1. Logs in `/var/log/fieldrino/`, `/var/log/gunicorn/`, `/var/log/celery/`
2. CloudWatch metrics and alarms
3. Troubleshooting section in DEPLOYMENT_GUIDE.md

## Cost Optimization

After 2-3 months of stable usage:
1. Purchase 1-year reserved instances
2. Save ~$13/month (31% discount)
3. No upfront payment required

## Architecture Diagram

```
Internet
   │
   ├─→ Route 53 (DNS)
   │      │
   │      ├─→ yourdomain.com → EC2
   │      ├─→ *.yourdomain.com → EC2 (wildcard)
   │      └─→ cdn.yourdomain.com → CloudFront
   │
   └─→ EC2 t3a.small
          ├─→ Nginx (reverse proxy)
          ├─→ Gunicorn (Django)
          ├─→ Celery Worker
          └─→ Celery Beat
          │
          ├─→ RDS PostgreSQL (database)
          ├─→ ElastiCache Redis (cache/queue)
          └─→ S3 + CloudFront (files/CDN)
```

## Security

✅ All data encrypted at rest
✅ TLS 1.2+ for all connections
✅ Security groups restrict access
✅ IAM roles (no hardcoded credentials)
✅ Automated backups enabled
✅ CloudWatch monitoring

## Scaling

When you need more capacity:

**Vertical Scaling** (easier):
- Upgrade to t3a.medium: +$13/month
- Upgrade RDS to db.t3.small: +$12/month

**Horizontal Scaling** (better):
- Add Load Balancer + 2nd EC2: +$30/month
- Enable RDS Multi-AZ: +$12/month
- Total HA setup: ~$90/month

---

**Ready to deploy? Start with Step 1!** 🚀
