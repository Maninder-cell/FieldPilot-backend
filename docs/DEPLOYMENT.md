# FieldRino - Deployment Guide

## Production Deployment on AWS

This guide covers deploying FieldRino to AWS using ECS Fargate, RDS, and other managed services.

## Architecture Overview

```
Route 53 → CloudFront → ALB → ECS Fargate (Django + Next.js)
                                    ↓
                          RDS PostgreSQL + ElastiCache Redis + S3
```

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Docker installed locally
- Domain name (for production)
- Stripe account (for payments)

## Infrastructure Setup

### 1. VPC & Networking

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Create subnets (public and private)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 --availability-zone us-east-1b

# Create Internet Gateway
aws ec2 create-internet-gateway
aws ec2 attach-internet-gateway --vpc-id vpc-xxx --internet-gateway-id igw-xxx
```

### 2. RDS PostgreSQL

```bash
# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name fieldrino-db-subnet \
  --db-subnet-group-description "FieldRino DB Subnet" \
  --subnet-ids subnet-xxx subnet-yyy

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier fieldrino-prod \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.4 \
  --master-username fieldrino \
  --master-user-password <secure-password> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --db-subnet-group-name fieldrino-db-subnet \
  --vpc-security-group-ids sg-xxx \
  --backup-retention-period 30 \
  --multi-az \
  --storage-encrypted \
  --enable-performance-insights
```

### 3. ElastiCache Redis

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id fieldrino-redis \
  --cache-node-type cache.t3.medium \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --cache-subnet-group-name fieldrino-cache-subnet \
  --security-group-ids sg-xxx
```

### 4. S3 Buckets

```bash
# Create S3 bucket for file storage
aws s3 mb s3://fieldrino-prod-files

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket fieldrino-prod-files \
  --versioning-configuration Status=Enabled

# Set CORS policy
aws s3api put-bucket-cors \
  --bucket fieldrino-prod-files \
  --cors-configuration file://cors-config.json

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket fieldrino-prod-files \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### 5. ECR Repositories

```bash
# Create ECR repositories
aws ecr create-repository --repository-name fieldrino/backend
aws ecr create-repository --repository-name fieldrino/frontend

# Get login credentials
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

## Docker Images

### Build and Push Backend

```bash
cd backend

# Build image
docker build -t fieldrino/backend:latest -f Dockerfile.prod .

# Tag for ECR
docker tag fieldrino/backend:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/backend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/backend:latest
```

### Build and Push Frontend

```bash
cd frontend

# Build image
docker build -t fieldrino/frontend:latest -f Dockerfile.prod .

# Tag for ECR
docker tag fieldrino/frontend:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/frontend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/frontend:latest
```

## ECS Setup

### 1. Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name fieldrino-prod
```

### 2. Task Definitions

**Backend Task Definition** (`backend-task-def.json`):

```json
{
  "family": "fieldrino-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::xxx:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::xxx:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"}
      ],
      "secrets": [
        {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fieldrino-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

**Frontend Task Definition** (`frontend-task-def.json`):

```json
{
  "family": "fieldrino-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::xxx:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/frontend:latest",
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "NODE_ENV", "value": "production"},
        {"name": "NEXT_PUBLIC_API_URL", "value": "https://api.fieldrino.com/api/v1"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fieldrino-frontend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 3. Create Services

```bash
# Register task definitions
aws ecs register-task-definition --cli-input-json file://backend-task-def.json
aws ecs register-task-definition --cli-input-json file://frontend-task-def.json

# Create backend service
aws ecs create-service \
  --cluster fieldrino-prod \
  --service-name backend \
  --task-definition fieldrino-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=8000"

# Create frontend service
aws ecs create-service \
  --cluster fieldrino-prod \
  --service-name frontend \
  --task-definition fieldrino-frontend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=frontend,containerPort=3000"
```

## Load Balancer Setup

### Create Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name fieldrino-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx \
  --scheme internet-facing

# Create target groups
aws elbv2 create-target-group \
  --name fieldrino-backend-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /health/

aws elbv2 create-target-group \
  --name fieldrino-frontend-tg \
  --protocol HTTP \
  --port 3000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /

# Create listeners
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

## CloudFront Setup

```bash
# Create CloudFront distribution
aws cloudfront create-distribution --distribution-config file://cloudfront-config.json
```

**cloudfront-config.json**:
```json
{
  "CallerReference": "fieldrino-prod-2025",
  "Aliases": {
    "Quantity": 2,
    "Items": ["fieldrino.com", "*.fieldrino.com"]
  },
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "frontend",
        "DomainName": "alb-xxx.us-east-1.elb.amazonaws.com",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only"
        }
      },
      {
        "Id": "api",
        "DomainName": "alb-xxx.us-east-1.elb.amazonaws.com",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only"
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "frontend",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 7,
      "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    },
    "Compress": true,
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000
  },
  "CacheBehaviors": {
    "Quantity": 1,
    "Items": [
      {
        "PathPattern": "/api/*",
        "TargetOriginId": "api",
        "ViewerProtocolPolicy": "https-only",
        "AllowedMethods": {
          "Quantity": 7,
          "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
        },
        "MinTTL": 0,
        "DefaultTTL": 0,
        "MaxTTL": 0
      }
    ]
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "arn:aws:acm:us-east-1:...",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  }
}
```

## Database Migrations

```bash
# Run migrations on production
aws ecs run-task \
  --cluster fieldrino-prod \
  --task-definition fieldrino-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["python", "manage.py", "migrate_schemas", "--shared"]
    }]
  }'

# Migrate tenant schemas
aws ecs run-task \
  --cluster fieldrino-prod \
  --task-definition fieldrino-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["python", "manage.py", "migrate_schemas", "--tenant"]
    }]
  }'
```

## Celery Workers

### Celery Worker Task Definition

```json
{
  "family": "fieldrino-celery-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::xxx:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "celery-worker",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/backend:latest",
      "command": ["celery", "-A", "config", "worker", "-l", "info"],
      "environment": [
        {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"}
      ],
      "secrets": [
        {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fieldrino-celery-worker",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Celery Beat Task Definition

```json
{
  "family": "fieldrino-celery-beat",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::xxx:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "celery-beat",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/fieldrino/backend:latest",
      "command": ["celery", "-A", "config", "beat", "-l", "info"],
      "environment": [
        {"name": "DJANGO_SETTINGS_MODULE", "value": "config.settings.production"}
      ],
      "secrets": [
        {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/fieldrino-celery-beat",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

## Monitoring & Logging

### CloudWatch Alarms

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name fieldrino-backend-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High memory alarm
aws cloudwatch put-metric-alarm \
  --alarm-name fieldrino-backend-high-memory \
  --alarm-description "Alert when memory exceeds 80%" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Application Monitoring (Sentry)

```python
# settings/production.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
    environment='production'
)
```

## Auto-Scaling

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/fieldrino-prod/backend \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/fieldrino-prod/backend \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'
```

## CI/CD Pipeline (GitHub Actions)

**.github/workflows/deploy.yml**:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push backend image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: fieldrino/backend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG -f Dockerfile.prod .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster fieldrino-prod \
            --service backend \
            --force-new-deployment

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push frontend image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: fieldrino/frontend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd frontend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG -f Dockerfile.prod .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster fieldrino-prod \
            --service frontend \
            --force-new-deployment
```

## Security Checklist

- [ ] Enable AWS WAF on CloudFront
- [ ] Configure security groups with minimal access
- [ ] Enable encryption at rest for RDS and S3
- [ ] Use AWS Secrets Manager for sensitive data
- [ ] Enable MFA for AWS root account
- [ ] Set up AWS CloudTrail for audit logging
- [ ] Configure VPC Flow Logs
- [ ] Enable GuardDuty for threat detection
- [ ] Regular security patches and updates
- [ ] Implement rate limiting on API
- [ ] Enable HTTPS only (redirect HTTP to HTTPS)
- [ ] Configure CORS properly
- [ ] Set up DDoS protection with AWS Shield

## Backup Strategy

```bash
# Automated RDS backups (already configured)
# Manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier fieldrino-prod \
  --db-snapshot-identifier fieldrino-manual-$(date +%Y%m%d)

# S3 versioning (already enabled)
# Cross-region replication
aws s3api put-bucket-replication \
  --bucket fieldrino-prod-files \
  --replication-configuration file://replication-config.json
```

## Rollback Procedure

```bash
# Rollback to previous task definition
aws ecs update-service \
  --cluster fieldrino-prod \
  --service backend \
  --task-definition fieldrino-backend:PREVIOUS_REVISION

# Rollback database migration
# Connect to RDS and run:
python manage.py migrate app_name migration_name
```

## Cost Optimization

- Use Reserved Instances for predictable workloads
- Enable S3 Intelligent-Tiering
- Use CloudFront caching aggressively
- Right-size ECS tasks based on metrics
- Use Spot Instances for Celery workers
- Set up AWS Budgets and alerts
- Review and delete unused resources regularly

## Post-Deployment Checklist

- [ ] Verify all services are running
- [ ] Test API endpoints
- [ ] Test frontend application
- [ ] Verify database connectivity
- [ ] Test file uploads to S3
- [ ] Verify Celery tasks are running
- [ ] Check CloudWatch logs
- [ ] Test email notifications
- [ ] Verify Stripe webhooks
- [ ] Test multi-tenant isolation
- [ ] Run smoke tests
- [ ] Monitor error rates
- [ ] Check performance metrics
