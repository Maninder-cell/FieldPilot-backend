#!/bin/bash
# FieldRino EC2 User Data Script
# This script runs on first boot to set up the application server

set -e

# Update system
apt-get update
apt-get upgrade -y

# Install required packages
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql-client \
    nginx \
    supervisor \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    libpq-dev \
    python3-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libpangocairo-1.0-0 \
    shared-mime-info

# Install CloudWatch Agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb

# Create application user
useradd -m -s /bin/bash fieldrino
usermod -aG sudo fieldrino

# Create application directory
mkdir -p /opt/fieldrino
chown fieldrino:fieldrino /opt/fieldrino

# Create log directories
mkdir -p /var/log/fieldrino
mkdir -p /var/log/gunicorn
mkdir -p /var/log/celery
mkdir -p /var/log/nginx
chown -R fieldrino:fieldrino /var/log/fieldrino
chown -R fieldrino:fieldrino /var/log/gunicorn
chown -R fieldrino:fieldrino /var/log/celery

# Clone repository (you'll need to set this up with deploy keys)
# For now, we'll create a placeholder
# cd /opt/fieldrino
# sudo -u fieldrino git clone <your-repo-url> app

# Create environment file
cat > /opt/fieldrino/.env << 'EOF'
# Django Settings
DEBUG=False
SECRET_KEY=${django_secret_key}
ALLOWED_HOSTS=.${domain_name},${domain_name}

# Database
DATABASE_URL=postgresql://${db_username}:${db_password}@${db_host}:5432/${db_name}

# Redis/Celery
CELERY_BROKER_URL=redis://${redis_host}:6379/0
CELERY_RESULT_BACKEND=redis://${redis_host}:6379/0
REDIS_URL=redis://${redis_host}:6379/0

# CORS
CORS_ALLOWED_ORIGINS=https://app.${domain_name},https://admin.${domain_name}
CORS_ALLOWED_DOMAIN=${domain_name}

# JWT
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=7

# Email (SES)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.${aws_region}.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=${email_host_user}
EMAIL_HOST_PASSWORD=${email_host_password}
DEFAULT_FROM_EMAIL=noreply@${domain_name}

# Stripe
STRIPE_SECRET_KEY=${stripe_secret_key}
STRIPE_PUBLISHABLE_KEY=${stripe_publishable_key}
STRIPE_WEBHOOK_SECRET=${stripe_webhook_secret}

# AWS S3
AWS_STORAGE_BUCKET_NAME=${s3_media_bucket}
AWS_S3_REGION_NAME=${aws_region}
AWS_S3_CUSTOM_DOMAIN=${cloudfront_domain}
AWS_DEFAULT_ACL=private
AWS_S3_FILE_OVERWRITE=False

# Static files
STATICFILES_STORAGE=storages.backends.s3boto3.S3StaticStorage
DEFAULT_FILE_STORAGE=storages.backends.s3boto3.S3Boto3Storage
EOF

chown fieldrino:fieldrino /opt/fieldrino/.env
chmod 600 /opt/fieldrino/.env

# Create Gunicorn configuration
cat > /opt/fieldrino/gunicorn.conf.py << 'EOF'
import multiprocessing

workers = 4
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
bind = "0.0.0.0:8000"
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
EOF

# Create Supervisor configuration
cat > /etc/supervisor/conf.d/fieldrino.conf << 'EOF'
[program:gunicorn]
command=/opt/fieldrino/venv/bin/gunicorn config.wsgi:application -c /opt/fieldrino/gunicorn.conf.py
directory=/opt/fieldrino/app
user=fieldrino
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/gunicorn/gunicorn.log

[program:celery-worker]
command=/opt/fieldrino/venv/bin/celery -A config worker -l info
directory=/opt/fieldrino/app
user=fieldrino
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log

[program:celery-beat]
command=/opt/fieldrino/venv/bin/celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/opt/fieldrino/app
user=fieldrino
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
EOF

# Create Nginx configuration
cat > /etc/nginx/sites-available/fieldrino << 'EOF'
upstream gunicorn {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name .${domain_name} ${domain_name};
    
    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name .${domain_name} ${domain_name};
    
    # SSL certificates (will be configured with Certbot)
    ssl_certificate /etc/letsencrypt/live/${domain_name}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${domain_name}/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    client_max_body_size 50M;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    location / {
        proxy_pass http://gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check endpoint
    location /health/ {
        proxy_pass http://gunicorn;
        access_log off;
    }
    
    access_log /var/log/nginx/fieldrino-access.log;
    error_log /var/log/nginx/fieldrino-error.log;
}
EOF

# Enable Nginx site
ln -sf /etc/nginx/sites-available/fieldrino /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Install Certbot for SSL
snap install --classic certbot
ln -s /snap/bin/certbot /usr/bin/certbot

# Note: SSL certificate setup needs to be done manually after DNS is configured:
# certbot --nginx -d ${domain_name} -d *.${domain_name}

# CloudWatch Agent configuration
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "metrics": {
    "namespace": "FieldRino/EC2",
    "metrics_collected": {
      "mem": {
        "measurement": [
          {"name": "mem_used_percent", "rename": "MemoryUsedPercent", "unit": "Percent"}
        ],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": [
          {"name": "used_percent", "rename": "DiskUsedPercent", "unit": "Percent"}
        ],
        "metrics_collection_interval": 60,
        "resources": ["*"]
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/gunicorn/error.log",
            "log_group_name": "/fieldrino/gunicorn",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/celery/worker.log",
            "log_group_name": "/fieldrino/celery",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/nginx/fieldrino-error.log",
            "log_group_name": "/fieldrino/nginx",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
EOF

# Start CloudWatch Agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Create deployment script
cat > /opt/fieldrino/deploy.sh << 'EOF'
#!/bin/bash
# Deployment script for FieldRino

set -e

echo "Starting deployment..."

# Navigate to app directory
cd /opt/fieldrino/app

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Activate virtual environment
source /opt/fieldrino/venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Restart services
echo "Restarting services..."
sudo supervisorctl restart gunicorn
sudo supervisorctl restart celery-worker
sudo supervisorctl restart celery-beat

echo "Deployment complete!"
EOF

chmod +x /opt/fieldrino/deploy.sh
chown fieldrino:fieldrino /opt/fieldrino/deploy.sh

# Reload Supervisor and Nginx
systemctl enable supervisor
systemctl start supervisor
systemctl enable nginx
systemctl restart nginx

echo "EC2 setup complete! Manual steps required:"
echo "1. Clone your application repository to /opt/fieldrino/app"
echo "2. Create Python virtual environment: python3.11 -m venv /opt/fieldrino/venv"
echo "3. Install dependencies: /opt/fieldrino/venv/bin/pip install -r /opt/fieldrino/app/requirements.txt"
echo "4. Run migrations: /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py migrate"
echo "5. Create superuser: /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py createsuperuser"
echo "6. Set up SSL with Certbot: certbot --nginx -d ${domain_name} -d *.${domain_name}"
echo "7. Start services: supervisorctl reread && supervisorctl update && supervisorctl start all"
