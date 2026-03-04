# Variables for FieldRino AWS Infrastructure

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-south-1"  # Mumbai - closest for India
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "fieldrino"
}

variable "domain_name" {
  description = "Primary domain name"
  type        = string
  # Set via terraform.tfvars or environment variable
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "fieldrino_db"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "fieldrino_admin"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
  # Set via terraform.tfvars or environment variable
}

variable "django_secret_key" {
  description = "Django secret key"
  type        = string
  sensitive   = true
  # Set via terraform.tfvars or environment variable
}

variable "stripe_secret_key" {
  description = "Stripe secret key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "stripe_publishable_key" {
  description = "Stripe publishable key"
  type        = string
  default     = ""
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "email_host_user" {
  description = "Email SMTP username"
  type        = string
  default     = ""
}

variable "email_host_password" {
  description = "Email SMTP password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ssh_key_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
  # Set via terraform.tfvars or environment variable
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into EC2"
  type        = string
  default     = "0.0.0.0/0"  # Restrict this to your IP in production
}

# Instance types (optimized for $40/month budget)
variable "ec2_instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3a.small"  # 2 vCPU, 2 GB RAM
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"  # 2 vCPU, 1 GB RAM
}

variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"  # 2 vCPU, 0.5 GB RAM
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "rds_max_allocated_storage" {
  description = "RDS maximum allocated storage for autoscaling"
  type        = number
  default     = 100
}
