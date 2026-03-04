# EC2 Instance for FieldRino Application Server

# Elastic IP for EC2
resource "aws_eip" "main" {
  domain = "vpc"
  
  tags = {
    Name = "${var.project_name}-eip"
  }
}

resource "aws_eip_association" "main" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.main.id
}

# IAM Role for EC2
resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

# IAM Policy for S3 Access
resource "aws_iam_role_policy" "s3_access" {
  name = "${var.project_name}-s3-access"
  role = aws_iam_role.ec2.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.media.arn,
          "${aws_s3_bucket.media.arn}/*",
          aws_s3_bucket.static.arn,
          "${aws_s3_bucket.static.arn}/*"
        ]
      }
    ]
  })
}

# IAM Policy for SES Access
resource "aws_iam_role_policy" "ses_access" {
  name = "${var.project_name}-ses-access"
  role = aws_iam_role.ec2.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach CloudWatch policy
resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

# User data script for EC2 initialization
data "template_file" "user_data" {
  template = file("${path.module}/user_data.sh")
  
  vars = {
    db_host               = aws_db_instance.main.address
    db_name               = var.db_name
    db_username           = var.db_username
    db_password           = var.db_password
    redis_host            = aws_elasticache_cluster.main.cache_nodes[0].address
    django_secret_key     = var.django_secret_key
    domain_name           = var.domain_name
    s3_media_bucket       = aws_s3_bucket.media.id
    s3_static_bucket      = aws_s3_bucket.static.id
    cloudfront_domain     = aws_cloudfront_distribution.main.domain_name
    stripe_secret_key     = var.stripe_secret_key
    stripe_publishable_key = var.stripe_publishable_key
    stripe_webhook_secret = var.stripe_webhook_secret
    email_host_user       = var.email_host_user
    email_host_password   = var.email_host_password
    aws_region            = var.aws_region
  }
}

# EC2 Instance
resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.ec2_instance_type
  key_name               = var.ssh_key_name
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = false
    encrypted             = true
  }
  
  user_data = data.template_file.user_data.rendered
  
  # Enable EC2 Auto Recovery
  monitoring = true
  
  tags = {
    Name = "${var.project_name}-app-server"
  }
  
  lifecycle {
    ignore_changes = [ami]
  }
}

# Get latest Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical
  
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# CloudWatch Alarm for EC2 Auto Recovery
resource "aws_cloudwatch_metric_alarm" "ec2_auto_recovery" {
  alarm_name          = "${var.project_name}-ec2-auto-recovery"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StatusCheckFailed_System"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "0"
  alarm_description   = "Trigger auto recovery when system status check fails"
  alarm_actions       = ["arn:aws:automate:${var.aws_region}:ec2:recover"]
  
  dimensions = {
    InstanceId = aws_instance.app.id
  }
}

# CloudWatch Alarm for High CPU
resource "aws_cloudwatch_metric_alarm" "ec2_high_cpu" {
  alarm_name          = "${var.project_name}-ec2-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Alert when CPU exceeds 80%"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    InstanceId = aws_instance.app.id
  }
}
