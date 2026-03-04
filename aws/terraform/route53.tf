# Route 53 DNS Configuration

# Hosted Zone (create manually or import existing)
# Uncomment if you want Terraform to create the hosted zone
# resource "aws_route53_zone" "main" {
#   name = var.domain_name
#   
#   tags = {
#     Name = "${var.project_name}-zone"
#   }
# }

# If you have an existing hosted zone, use data source:
data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false
}

# A Record for main domain -> EC2
resource "aws_route53_record" "main" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.main.public_ip]
}

# Wildcard A Record for tenant subdomains -> EC2
resource "aws_route53_record" "wildcard" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "*.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.main.public_ip]
}

# API subdomain -> EC2
resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.main.public_ip]
}

# CDN subdomain -> CloudFront
resource "aws_route53_record" "cdn" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "cdn.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [aws_cloudfront_distribution.main.domain_name]
}
