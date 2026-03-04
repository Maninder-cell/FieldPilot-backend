#!/bin/bash
# FieldRino Deployment Script
# Run this script to deploy updates to your EC2 instance

set -e

echo "========================================="
echo "FieldRino Deployment"
echo "========================================="
echo ""

# Get EC2 IP from Terraform output
cd "$(dirname "$0")/../terraform"
EC2_IP=$(terraform output -raw ec2_public_ip 2>/dev/null)

if [ -z "$EC2_IP" ]; then
    echo "Error: Could not get EC2 IP from Terraform output."
    echo "Make sure you have run 'terraform apply' first."
    exit 1
fi

echo "Deploying to: $EC2_IP"
echo ""

# Get SSH key name
SSH_KEY=$(terraform output -json | jq -r '.ssh_command.value' | grep -oP '(?<=-i ~/.ssh/)[^ ]+')

if [ -z "$SSH_KEY" ]; then
    echo "Error: Could not determine SSH key."
    exit 1
fi

echo "Using SSH key: ~/.ssh/$SSH_KEY"
echo ""

# Take RDS snapshot before deployment
echo "Creating RDS snapshot before deployment..."
SNAPSHOT_NAME="fieldrino-pre-deploy-$(date +%Y%m%d-%H%M%S)"
RDS_INSTANCE=$(terraform output -json | jq -r '.rds_endpoint.value' | cut -d: -f1)

aws rds create-db-snapshot \
    --db-instance-identifier "$RDS_INSTANCE" \
    --db-snapshot-identifier "$SNAPSHOT_NAME" \
    --region ap-south-1

echo "✓ Snapshot created: $SNAPSHOT_NAME"
echo ""

# SSH into EC2 and run deployment
echo "Connecting to EC2 and running deployment..."
ssh -i ~/.ssh/$SSH_KEY ubuntu@$EC2_IP << 'ENDSSH'
    set -e
    
    echo "Starting deployment on EC2..."
    
    # Run the deployment script
    sudo -u fieldrino /opt/fieldrino/deploy.sh
    
    echo "Deployment complete!"
ENDSSH

echo ""
echo "========================================="
echo "Deployment Successful!"
echo "========================================="
echo ""
echo "Verifying application health..."

# Check health endpoint
sleep 5
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" https://yourdomain.com/api/health/ || echo "000")

if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✓ Health check passed!"
else
    echo "⚠ Health check failed (HTTP $HEALTH_CHECK)"
    echo "Please check the application logs."
fi

echo ""
echo "Deployment completed at: $(date)"
echo ""
