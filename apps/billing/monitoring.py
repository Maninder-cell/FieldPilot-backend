"""
Billing Monitoring and Metrics

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.

This module provides monitoring utilities for the Stripe billing system.
"""
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Subscription

logger = logging.getLogger(__name__)


class BillingMetrics:
    """
    Utility class for collecting billing metrics and monitoring data.
    """
    
    @staticmethod
    def get_subscription_metrics():
        """
        Get current subscription metrics.
        
        Returns:
            dict: Subscription metrics including counts by status
        """
        try:
            total = Subscription.objects.count()
            active = Subscription.objects.filter(status='active').count()
            trialing = Subscription.objects.filter(status='trialing').count()
            past_due = Subscription.objects.filter(status='past_due').count()
            canceled = Subscription.objects.filter(status='canceled').count()
            
            return {
                'total_subscriptions': total,
                'active_subscriptions': active,
                'trialing_subscriptions': trialing,
                'past_due_subscriptions': past_due,
                'canceled_subscriptions': canceled,
                'active_percentage': (active / total * 100) if total > 0 else 0,
                'churn_rate': (canceled / total * 100) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error collecting subscription metrics: {str(e)}")
            return {}
    
    @staticmethod
    def get_payment_health_metrics():
        """
        Get payment health metrics.
        
        Returns:
            dict: Payment health indicators
        """
        try:
            total_active = Subscription.objects.filter(
                status__in=['active', 'trialing']
            ).count()
            
            past_due = Subscription.objects.filter(status='past_due').count()
            
            # Calculate payment failure rate
            failure_rate = (past_due / total_active * 100) if total_active > 0 else 0
            
            return {
                'total_active_subscriptions': total_active,
                'past_due_subscriptions': past_due,
                'payment_failure_rate': failure_rate,
                'payment_health_status': 'healthy' if failure_rate < 5 else 'warning' if failure_rate < 10 else 'critical'
            }
        except Exception as e:
            logger.error(f"Error collecting payment health metrics: {str(e)}")
            return {}
    
    @staticmethod
    def get_trial_conversion_metrics():
        """
        Get trial conversion metrics.
        
        Returns:
            dict: Trial conversion statistics
        """
        try:
            # Get subscriptions that were created in the last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            recent_subscriptions = Subscription.objects.filter(
                created_at__gte=thirty_days_ago
            )
            
            total_recent = recent_subscriptions.count()
            converted = recent_subscriptions.filter(status='active').count()
            still_trialing = recent_subscriptions.filter(status='trialing').count()
            
            conversion_rate = (converted / total_recent * 100) if total_recent > 0 else 0
            
            return {
                'total_trials_last_30_days': total_recent,
                'converted_to_paid': converted,
                'still_trialing': still_trialing,
                'trial_conversion_rate': conversion_rate
            }
        except Exception as e:
            logger.error(f"Error collecting trial conversion metrics: {str(e)}")
            return {}
    
    @staticmethod
    def get_revenue_metrics():
        """
        Get revenue metrics based on active subscriptions.
        
        Returns:
            dict: Revenue statistics
        """
        try:
            from django.db.models import Sum, F, Case, When, DecimalField
            
            # Calculate MRR (Monthly Recurring Revenue)
            subscriptions = Subscription.objects.filter(status='active')
            
            mrr = 0
            arr = 0
            
            for sub in subscriptions:
                # This is an approximation - actual revenue is in Stripe
                monthly_value = float(sub.plan.price_monthly)
                mrr += monthly_value
                arr += monthly_value * 12
            
            return {
                'monthly_recurring_revenue': mrr,
                'annual_recurring_revenue': arr,
                'active_paying_customers': subscriptions.count(),
                'note': 'Revenue metrics are estimates. Check Stripe dashboard for actual revenue.'
            }
        except Exception as e:
            logger.error(f"Error collecting revenue metrics: {str(e)}")
            return {}
    
    @staticmethod
    def check_alerts():
        """
        Check for conditions that should trigger alerts.
        
        Returns:
            list: List of alert conditions that are triggered
        """
        alerts = []
        
        try:
            # Check payment failure rate
            health_metrics = BillingMetrics.get_payment_health_metrics()
            failure_rate = health_metrics.get('payment_failure_rate', 0)
            
            if failure_rate > 10:
                alerts.append({
                    'severity': 'critical',
                    'type': 'payment_failure_rate',
                    'message': f'Payment failure rate is {failure_rate:.1f}% (threshold: 10%)',
                    'value': failure_rate
                })
            elif failure_rate > 5:
                alerts.append({
                    'severity': 'warning',
                    'type': 'payment_failure_rate',
                    'message': f'Payment failure rate is {failure_rate:.1f}% (threshold: 5%)',
                    'value': failure_rate
                })
            
            # Check for subscriptions stuck in past_due
            past_due_count = Subscription.objects.filter(status='past_due').count()
            if past_due_count > 0:
                alerts.append({
                    'severity': 'warning',
                    'type': 'past_due_subscriptions',
                    'message': f'{past_due_count} subscriptions are past due',
                    'value': past_due_count
                })
            
            # Check for low trial conversion rate
            trial_metrics = BillingMetrics.get_trial_conversion_metrics()
            conversion_rate = trial_metrics.get('trial_conversion_rate', 0)
            
            if conversion_rate < 20 and trial_metrics.get('total_trials_last_30_days', 0) > 10:
                alerts.append({
                    'severity': 'warning',
                    'type': 'low_trial_conversion',
                    'message': f'Trial conversion rate is {conversion_rate:.1f}% (threshold: 20%)',
                    'value': conversion_rate
                })
            
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
            alerts.append({
                'severity': 'error',
                'type': 'monitoring_error',
                'message': f'Error checking alerts: {str(e)}',
                'value': None
            })
        
        return alerts
    
    @staticmethod
    def log_stripe_api_call(method: str, endpoint: str, success: bool, duration_ms: float = None):
        """
        Log Stripe API call for monitoring.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Stripe API endpoint
            success: Whether the call succeeded
            duration_ms: Duration in milliseconds
        """
        log_data = {
            'method': method,
            'endpoint': endpoint,
            'success': success,
            'duration_ms': duration_ms
        }
        
        if success:
            logger.info(f"Stripe API call succeeded: {method} {endpoint} ({duration_ms}ms)", extra=log_data)
        else:
            logger.error(f"Stripe API call failed: {method} {endpoint}", extra=log_data)


def get_billing_dashboard_data():
    """
    Get comprehensive billing dashboard data.
    
    Returns:
        dict: Complete dashboard data including metrics and alerts
    """
    return {
        'subscription_metrics': BillingMetrics.get_subscription_metrics(),
        'payment_health': BillingMetrics.get_payment_health_metrics(),
        'trial_conversion': BillingMetrics.get_trial_conversion_metrics(),
        'revenue_metrics': BillingMetrics.get_revenue_metrics(),
        'alerts': BillingMetrics.check_alerts(),
        'timestamp': timezone.now().isoformat()
    }
