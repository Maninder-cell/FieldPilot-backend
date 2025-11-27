"""
Management command to check billing system health and display metrics.

Usage:
    python manage.py check_billing_health [--alerts-only]
"""
from django.core.management.base import BaseCommand
from apps.billing.monitoring import BillingMetrics, get_billing_dashboard_data
import json


class Command(BaseCommand):
    help = 'Check billing system health and display metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--alerts-only',
            action='store_true',
            help='Only show alerts, not full metrics',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format',
        )

    def handle(self, *args, **options):
        alerts_only = options['alerts_only']
        json_output = options['json']
        
        if alerts_only:
            # Only check and display alerts
            alerts = BillingMetrics.check_alerts()
            
            if json_output:
                self.stdout.write(json.dumps({'alerts': alerts}, indent=2))
                return
            
            if not alerts:
                self.stdout.write(self.style.SUCCESS('✓ No alerts - billing system is healthy'))
                return
            
            self.stdout.write(self.style.WARNING(f'Found {len(alerts)} alert(s):'))
            self.stdout.write('')
            
            for alert in alerts:
                severity = alert['severity']
                if severity == 'critical':
                    style = self.style.ERROR
                    icon = '✗'
                elif severity == 'warning':
                    style = self.style.WARNING
                    icon = '⚠'
                else:
                    style = self.style.NOTICE
                    icon = 'ℹ'
                
                self.stdout.write(style(f'{icon} [{severity.upper()}] {alert["message"]}'))
            
            return
        
        # Full dashboard
        dashboard = get_billing_dashboard_data()
        
        if json_output:
            self.stdout.write(json.dumps(dashboard, indent=2, default=str))
            return
        
        # Display formatted output
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('Billing System Health Dashboard'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write('')
        
        # Subscription Metrics
        sub_metrics = dashboard['subscription_metrics']
        self.stdout.write(self.style.HTTP_INFO('📊 Subscription Metrics'))
        self.stdout.write(f"  Total Subscriptions: {sub_metrics.get('total_subscriptions', 0)}")
        self.stdout.write(f"  Active: {sub_metrics.get('active_subscriptions', 0)}")
        self.stdout.write(f"  Trialing: {sub_metrics.get('trialing_subscriptions', 0)}")
        self.stdout.write(f"  Past Due: {sub_metrics.get('past_due_subscriptions', 0)}")
        self.stdout.write(f"  Canceled: {sub_metrics.get('canceled_subscriptions', 0)}")
        self.stdout.write(f"  Active Rate: {sub_metrics.get('active_percentage', 0):.1f}%")
        self.stdout.write(f"  Churn Rate: {sub_metrics.get('churn_rate', 0):.1f}%")
        self.stdout.write('')
        
        # Payment Health
        payment_health = dashboard['payment_health']
        health_status = payment_health.get('payment_health_status', 'unknown')
        if health_status == 'healthy':
            status_style = self.style.SUCCESS
            icon = '✓'
        elif health_status == 'warning':
            status_style = self.style.WARNING
            icon = '⚠'
        else:
            status_style = self.style.ERROR
            icon = '✗'
        
        self.stdout.write(self.style.HTTP_INFO('💳 Payment Health'))
        self.stdout.write(status_style(f"  Status: {icon} {health_status.upper()}"))
        self.stdout.write(f"  Active Subscriptions: {payment_health.get('total_active_subscriptions', 0)}")
        self.stdout.write(f"  Past Due: {payment_health.get('past_due_subscriptions', 0)}")
        self.stdout.write(f"  Failure Rate: {payment_health.get('payment_failure_rate', 0):.1f}%")
        self.stdout.write('')
        
        # Trial Conversion
        trial_metrics = dashboard['trial_conversion']
        self.stdout.write(self.style.HTTP_INFO('🎯 Trial Conversion (Last 30 Days)'))
        self.stdout.write(f"  Total Trials: {trial_metrics.get('total_trials_last_30_days', 0)}")
        self.stdout.write(f"  Converted to Paid: {trial_metrics.get('converted_to_paid', 0)}")
        self.stdout.write(f"  Still Trialing: {trial_metrics.get('still_trialing', 0)}")
        self.stdout.write(f"  Conversion Rate: {trial_metrics.get('trial_conversion_rate', 0):.1f}%")
        self.stdout.write('')
        
        # Revenue Metrics
        revenue = dashboard['revenue_metrics']
        self.stdout.write(self.style.HTTP_INFO('💰 Revenue Metrics (Estimated)'))
        self.stdout.write(f"  MRR: ${revenue.get('monthly_recurring_revenue', 0):,.2f}")
        self.stdout.write(f"  ARR: ${revenue.get('annual_recurring_revenue', 0):,.2f}")
        self.stdout.write(f"  Paying Customers: {revenue.get('active_paying_customers', 0)}")
        self.stdout.write(self.style.NOTICE(f"  Note: {revenue.get('note', '')}"))
        self.stdout.write('')
        
        # Alerts
        alerts = dashboard['alerts']
        if alerts:
            self.stdout.write(self.style.WARNING(f'⚠ Active Alerts ({len(alerts)})'))
            for alert in alerts:
                severity = alert['severity']
                if severity == 'critical':
                    style = self.style.ERROR
                elif severity == 'warning':
                    style = self.style.WARNING
                else:
                    style = self.style.NOTICE
                
                self.stdout.write(style(f"  • {alert['message']}"))
            self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('✓ No Active Alerts'))
            self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('='*60))
