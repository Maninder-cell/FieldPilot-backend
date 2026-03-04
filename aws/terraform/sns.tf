# SNS Topic for CloudWatch Alarms

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
  
  tags = {
    Name = "${var.project_name}-alerts"
  }
}

# SNS Topic Subscription (Email)
# You need to confirm the subscription via email after applying
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.email_host_user  # Use your admin email
}

# Optional: SMS subscription (additional cost)
# resource "aws_sns_topic_subscription" "alerts_sms" {
#   topic_arn = aws_sns_topic.alerts.arn
#   protocol  = "sms"
#   endpoint  = "+1234567890"  # Your phone number
# }
