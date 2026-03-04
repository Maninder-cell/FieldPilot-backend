# FieldRino AWS Quick Reference

Quick commands and information for managing your AWS deployment.

## SSH Access

```bash
# SSH into EC2
ssh -i ~/.ssh/fieldrino-prod.pem ubuntu@<EC2_IP>

# Get EC2 IP from Terraform
cd aws/terraform
terraform output ec2_public_ip
```

## Service Management

```bash
# Check service status
sudo supervisorctl status

# Start all services
sudo supervisorctl start all

# Stop all services
sudo supervisorctl stop all

# Restart specific service
sudo supervisorctl restart gunicorn
sudo supervisorctl restart celery-worker
sudo supervisorctl restart celery-beat

# Reload Supervisor configuration
sudo supervisorctl reread
sudo supervisorctl update

# View service logs
sudo supervisorctl tail gunicorn stderr
sudo supervisorctl tail celery-worker stderr
```

## Application Management

```bash
# Navigate to app directory
cd /opt/fieldrino/app

# Activate virtual environment
source /opt/fieldrino/venv/bin/activate

# Run Django management commands
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py shell

# Check Django configuration
python manage.py check --deploy
```

## Deployment

```bash
# Quick deployment (from local machine)
cd aws
./scripts/deploy.sh

# Manual deployment (on EC2)
sudo -u fieldrino /opt/fieldrino/deploy.sh

# Or step by step:
cd /opt/fieldrino/app
git pull origin main
source /opt/fieldrino/venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo supervisorctl restart gunicorn
sudo supervisorctl restart celery-worker
```

## Database Management

```bash
# Connect to RDS
psql -h <RDS_ENDPOINT> -U fieldrino_admin -d fieldrino_db

# Create database backup
pg_dump -h <RDS_ENDPOINT> -U fieldrino_admin fieldrino_db > backup.sql

# Restore from backup
psql -h <RDS_ENDPOINT> -U fieldrino_admin fieldrino_db < backup.sql

# Create RDS snapshot (AWS CLI)
aws rds create-db-snapshot \
  --db-instance-identifier fieldrino-db \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)

# List RDS snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier fieldrino-db
```

## Log Management

```bash
# Application logs
sudo tail -f /var/log/fieldrino/django.log
sudo tail -f /var/log/fieldrino/django-error.log

# Gunicorn logs
sudo tail -f /var/log/gunicorn/access.log
sudo tail -f /var/log/gunicorn/error.log

# Celery logs
sudo tail -f /var/log/celery/worker.log
sudo tail -f /var/log/celery/beat.log

# Nginx logs
sudo tail -f /var/log/nginx/fieldrino-access.log
sudo tail -f /var/log/nginx/fieldrino-error.log

# System logs
sudo tail -f /var/log/syslog
sudo journalctl -u nginx -f
```

## Nginx Management

```bash
# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx

# Check Nginx status
sudo systemctl status nginx

# View Nginx error log
sudo tail -f /var/log/nginx/error.log
```

## SSL Certificate Management

```bash
# Renew SSL certificate
sudo certbot renew

# Force renew
sudo certbot renew --force-renewal

# Test renewal
sudo certbot renew --dry-run

# List certificates
sudo certbot certificates

# Revoke certificate
sudo certbot revoke --cert-path /etc/letsencrypt/live/domain.com/cert.pem
```

## Redis Management

```bash
# Connect to Redis
redis-cli -h <REDIS_ENDPOINT>

# Check Redis info
redis-cli -h <REDIS_ENDPOINT> info

# Monitor Redis commands
redis-cli -h <REDIS_ENDPOINT> monitor

# Clear all Redis data (DANGEROUS!)
redis-cli -h <REDIS_ENDPOINT> FLUSHALL

# Check Celery queue length
redis-cli -h <REDIS_ENDPOINT> LLEN celery
```

## Monitoring

```bash
# Check disk space
df -h

# Check memory usage
free -h

# Check CPU usage
top
htop

# Check running processes
ps aux | grep gunicorn
ps aux | grep celery
ps aux | grep nginx

# Check network connections
netstat -tulpn | grep LISTEN

# Check system load
uptime
```

## AWS CLI Commands

```bash
# Get EC2 instance info
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=fieldrino-app-server"

# Get RDS instance info
aws rds describe-db-instances \
  --db-instance-identifier fieldrino-db

# Get ElastiCache cluster info
aws elasticache describe-cache-clusters \
  --cache-cluster-id fieldrino-redis

# List S3 buckets
aws s3 ls

# Sync files to S3
aws s3 sync /local/path s3://bucket-name/

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <DISTRIBUTION_ID> \
  --paths "/*"

# View CloudWatch logs
aws logs tail /fieldrino/gunicorn --follow
```

## Terraform Commands

```bash
# Navigate to Terraform directory
cd aws/terraform

# Initialize Terraform
terraform init

# Plan changes
terraform plan

# Apply changes
terraform apply

# Show current state
terraform show

# List resources
terraform state list

# Get outputs
terraform output

# Destroy infrastructure (DANGEROUS!)
terraform destroy
```

## Health Checks

```bash
# Check application health
curl https://yourdomain.com/api/health/

# Check with details
curl -v https://yourdomain.com/api/health/

# Check from EC2
curl http://localhost:8000/api/health/

# Check SSL certificate
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Check DNS resolution
dig yourdomain.com
dig *.yourdomain.com
```

## Troubleshooting

```bash
# Check if services are running
sudo supervisorctl status

# Check if ports are listening
sudo netstat -tulpn | grep :8000  # Gunicorn
sudo netstat -tulpn | grep :80    # Nginx HTTP
sudo netstat -tulpn | grep :443   # Nginx HTTPS

# Check database connectivity
python manage.py dbshell

# Check Redis connectivity
redis-cli -h <REDIS_ENDPOINT> ping

# Check S3 access
aws s3 ls s3://your-bucket-name/

# Check environment variables
cat /opt/fieldrino/.env

# Check Python packages
/opt/fieldrino/venv/bin/pip list

# Check Django settings
python manage.py diffsettings
```

## Performance Monitoring

```bash
# Check database connections
psql -h <RDS_ENDPOINT> -U fieldrino_admin -d fieldrino_db \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Check slow queries
psql -h <RDS_ENDPOINT> -U fieldrino_admin -d fieldrino_db \
  -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check Celery queue length
redis-cli -h <REDIS_ENDPOINT> LLEN celery

# Check memory usage by process
ps aux --sort=-%mem | head

# Check CPU usage by process
ps aux --sort=-%cpu | head
```

## Backup & Restore

```bash
# Create manual RDS snapshot
aws rds create-db-snapshot \
  --db-instance-identifier fieldrino-db \
  --db-snapshot-identifier backup-$(date +%Y%m%d-%H%M%S)

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier fieldrino-db-restored \
  --db-snapshot-identifier backup-20240304-120000

# Backup application files
tar -czf /tmp/app-backup-$(date +%Y%m%d).tar.gz /opt/fieldrino/app

# Backup environment file
sudo cp /opt/fieldrino/.env /opt/fieldrino/.env.backup
```

## Security

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Check for security updates
sudo apt list --upgradable

# Check open ports
sudo netstat -tulpn

# Check firewall rules (if using UFW)
sudo ufw status

# Check failed login attempts
sudo grep "Failed password" /var/log/auth.log

# Check sudo usage
sudo grep sudo /var/log/auth.log
```

## Cost Monitoring

```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost

# Get cost by service
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE
```

## Emergency Procedures

```bash
# Restart all services
sudo supervisorctl restart all
sudo systemctl restart nginx

# Reboot server (last resort)
sudo reboot

# Rollback deployment
cd /opt/fieldrino/app
git reset --hard HEAD~1
sudo supervisorctl restart all

# Restore from RDS snapshot
# 1. Create new RDS instance from snapshot
# 2. Update .env with new endpoint
# 3. Restart services
```

## Useful Aliases

Add these to `~/.bashrc` on EC2:

```bash
alias app='cd /opt/fieldrino/app'
alias venv='source /opt/fieldrino/venv/bin/activate'
alias manage='python /opt/fieldrino/app/manage.py'
alias logs='sudo tail -f /var/log/fieldrino/django.log'
alias errors='sudo tail -f /var/log/fieldrino/django-error.log'
alias services='sudo supervisorctl status'
alias restart='sudo supervisorctl restart all'
```

## Important Files & Directories

```
/opt/fieldrino/              # Application root
├── app/                     # Django application
├── venv/                    # Python virtual environment
├── .env                     # Environment variables
├── gunicorn.conf.py         # Gunicorn configuration
└── deploy.sh                # Deployment script

/var/log/fieldrino/          # Application logs
/var/log/gunicorn/           # Gunicorn logs
/var/log/celery/             # Celery logs
/var/log/nginx/              # Nginx logs

/etc/nginx/                  # Nginx configuration
/etc/supervisor/conf.d/      # Supervisor configuration
/etc/letsencrypt/            # SSL certificates
```

## Support Contacts

- **AWS Support**: https://console.aws.amazon.com/support/
- **Terraform Issues**: https://github.com/hashicorp/terraform/issues
- **Django Documentation**: https://docs.djangoproject.com/
- **Celery Documentation**: https://docs.celeryproject.org/

---

**Keep this reference handy for quick access to common commands!**
