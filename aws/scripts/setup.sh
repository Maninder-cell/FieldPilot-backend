#!/bin/bash
# FieldRino AWS Setup Script
# This script helps you set up the AWS infrastructure

set -e

echo "========================================="
echo "FieldRino AWS Infrastructure Setup"
echo "========================================="
echo ""

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "Error: Terraform is not installed."
    echo "Please install Terraform: https://www.terraform.io/downloads"
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed."
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured."
    echo "Please run: aws configure"
    exit 1
fi

echo "✓ AWS credentials configured"
echo ""

# Navigate to terraform directory
cd "$(dirname "$0")/../terraform"

# Check if terraform.tfvars exists
if [ ! -f "terraform.tfvars" ]; then
    echo "Error: terraform.tfvars not found."
    echo "Please copy terraform.tfvars.example to terraform.tfvars and fill in your values:"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    echo "  nano terraform.tfvars"
    exit 1
fi

echo "✓ terraform.tfvars found"
echo ""

# Initialize Terraform
echo "Initializing Terraform..."
terraform init

echo ""
echo "========================================="
echo "Pre-deployment Checklist"
echo "========================================="
echo ""
echo "Before running 'terraform apply', ensure you have:"
echo ""
echo "1. ✓ Created an EC2 key pair in AWS console"
echo "2. ✓ Registered your domain name"
echo "3. ✓ Created a Route 53 hosted zone (or have existing one)"
echo "4. ✓ Generated strong passwords for database and Django"
echo "5. ✓ Obtained Stripe API keys (if using billing)"
echo "6. ✓ Configured email SMTP credentials"
echo "7. ✓ Updated terraform.tfvars with all values"
echo ""
echo "========================================="
echo ""

read -p "Have you completed all the above steps? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Please complete the checklist before proceeding."
    exit 1
fi

echo ""
echo "Running Terraform plan..."
terraform plan -out=tfplan

echo ""
echo "========================================="
echo "Review the plan above carefully!"
echo "========================================="
echo ""
read -p "Do you want to apply this plan? (yes/no): " apply_confirm

if [ "$apply_confirm" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "Applying Terraform configuration..."
terraform apply tfplan

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. SSH into your EC2 instance:"
terraform output ssh_command
echo ""
echo "2. Clone your application repository:"
echo "   cd /opt/fieldrino"
echo "   sudo -u fieldrino git clone <your-repo-url> app"
echo ""
echo "3. Set up Python virtual environment:"
echo "   sudo -u fieldrino python3.11 -m venv /opt/fieldrino/venv"
echo ""
echo "4. Install dependencies:"
echo "   sudo -u fieldrino /opt/fieldrino/venv/bin/pip install -r /opt/fieldrino/app/requirements.txt"
echo ""
echo "5. Run migrations:"
echo "   sudo -u fieldrino /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py migrate"
echo ""
echo "6. Create superuser:"
echo "   sudo -u fieldrino /opt/fieldrino/venv/bin/python /opt/fieldrino/app/manage.py createsuperuser"
echo ""
echo "7. Set up SSL certificate:"
echo "   sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com"
echo ""
echo "8. Start services:"
echo "   sudo supervisorctl reread"
echo "   sudo supervisorctl update"
echo "   sudo supervisorctl start all"
echo ""
echo "9. Confirm SNS email subscription (check your email)"
echo ""
echo "Important outputs:"
terraform output
echo ""
echo "Save these outputs securely!"
echo ""
