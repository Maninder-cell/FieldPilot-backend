# Terraform Outputs

output "ec2_public_ip" {
  description = "EC2 Elastic IP address"
  value       = aws_eip.main.public_ip
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL address"
  value       = aws_db_instance.main.address
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = "${aws_elasticache_cluster.main.cache_nodes[0].address}:${aws_elasticache_cluster.main.cache_nodes[0].port}"
}

output "redis_address" {
  description = "ElastiCache Redis address"
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "s3_media_bucket" {
  description = "S3 media bucket name"
  value       = aws_s3_bucket.media.id
}

output "s3_static_bucket" {
  description = "S3 static bucket name"
  value       = aws_s3_bucket.static.id
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "ssh_command" {
  description = "SSH command to connect to EC2"
  value       = "ssh -i ~/.ssh/${var.ssh_key_name}.pem ubuntu@${aws_eip.main.public_ip}"
}

output "database_url" {
  description = "Database connection URL (for Django)"
  value       = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.main.address}:5432/${var.db_name}"
  sensitive   = true
}

output "redis_url" {
  description = "Redis connection URL (for Django)"
  value       = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0"
}
