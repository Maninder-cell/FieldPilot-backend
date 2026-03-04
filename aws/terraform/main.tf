# FieldRino AWS Infrastructure - $40/month Budget
# Terraform configuration for production deployment

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Remote state backend (optional - comment out for first deployment)
  # Uncomment and configure after creating S3 bucket for state storage
  # backend "s3" {
  #   bucket = "fieldrino-terraform-state"
  #   key    = "production/terraform.tfstate"
  #   region = "eu-west-2"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "FieldRino"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}
