# Route 53 DNS Configuration

# NOTE: Route 53 configuration is commented out for initial deployment
# You can either:
# 1. Create a Route 53 hosted zone manually in AWS Console first, then uncomment
# 2. Use your existing domain registrar's DNS
# 3. Uncomment the resource below to let Terraform create the hosted zone

# Option 1: Let Terraform create the hosted zone
# Uncomment this block to create a new hosted zone
# resource "aws_route53_zone" "main" {
#   name = var.domain_name
#   
#   tags = {
#     Name = "${var.project_name}-zone"
#   }
# }

# Option 2: Use existing hosted zone
# Uncomment this block if you already have a hosted zone
# data "aws_route53_zone" "main" {
#   name         = var.domain_name
#   private_zone = false
# }

# DNS Records (uncomment after creating hosted zone)
# A Record for main domain -> EC2
# resource "aws_route53_record" "main" {
#   zone_id = data.aws_route53_zone.main.zone_id  # or aws_route53_zone.main.zone_id
#   name    = var.domain_name
#   type    = "A"
#   ttl     = 300
#   records = [aws_eip.main.public_ip]
# }

# Wildcard A Record for tenant subdomains -> EC2
# resource "aws_route53_record" "wildcard" {
#   zone_id = data.aws_route53_zone.main.zone_id  # or aws_route53_zone.main.zone_id
#   name    = "*.${var.domain_name}"
#   type    = "A"
#   ttl     = 300
#   records = [aws_eip.main.public_ip]
# }

# API subdomain -> EC2
# resource "aws_route53_record" "api" {
#   zone_id = data.aws_route53_zone.main.zone_id  # or aws_route53_zone.main.zone_id
#   name    = "api.${var.domain_name}"
#   type    = "A"
#   ttl     = 300
#   records = [aws_eip.main.public_ip]
# }

# CDN subdomain -> CloudFront
# resource "aws_route53_record" "cdn" {
#   zone_id = data.aws_route53_zone.main.zone_id  # or aws_route53_zone.main.zone_id
#   name    = "cdn.${var.domain_name}"
#   type    = "CNAME"
#   ttl     = 300
#   records = [aws_cloudfront_distribution.main.domain_name]
# }
