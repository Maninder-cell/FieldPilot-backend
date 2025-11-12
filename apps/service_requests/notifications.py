"""
Service Request Notification Service

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class RequestNotificationService:
    """
    Handle notifications for service requests.
    Task 14.1: RequestNotificationService class
    """
    
    @staticmethod
    def notify_request_created(service_request):
        """
        Send notifications when request is created.
        Notifies customer (confirmation) and admins (new request alert).
        """
        try:
            # Notify customer
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Service Request {service_request.request_number} Received',
                template='service_requests/emails/request_created_customer.html',
                context={
                    'request': service_request,
                    'customer_name': service_request.customer.full_name,
                }
            )
            
            # Notify admins/managers
            from apps.authentication.models import User
            admins = User.objects.filter(
                role__in=['admin', 'manager'],
                is_active=True
            )
            
            for admin in admins:
                RequestNotificationService._send_admin_email(
                    to_email=admin.email,
                    subject=f'New Service Request: {service_request.request_number}',
                    template='service_requests/emails/request_created_admin.html',
                    context={
                        'request': service_request,
                        'admin_name': admin.full_name,
                    }
                )
            
            logger.info(f"Notifications sent for request creation: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send request creation notifications: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_request_accepted(service_request):
        """
        Send notification when request is accepted.
        """
        try:
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Service Request {service_request.request_number} Accepted',
                template='service_requests/emails/request_accepted.html',
                context={
                    'request': service_request,
                    'customer_name': service_request.customer.full_name,
                    'estimated_timeline': service_request.estimated_timeline,
                    'response_message': service_request.response_message,
                }
            )
            
            logger.info(f"Acceptance notification sent: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send acceptance notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_request_rejected(service_request):
        """
        Send notification when request is rejected.
        """
        try:
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Service Request {service_request.request_number} Update',
                template='service_requests/emails/request_rejected.html',
                context={
                    'request': service_request,
                    'customer_name': service_request.customer.full_name,
                    'rejection_reason': service_request.rejection_reason,
                }
            )
            
            logger.info(f"Rejection notification sent: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send rejection notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_task_created(service_request, task):
        """
        Send notification when task is created from request.
        """
        try:
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Work Scheduled for Request {service_request.request_number}',
                template='service_requests/emails/task_created.html',
                context={
                    'request': service_request,
                    'task': task,
                    'customer_name': service_request.customer.full_name,
                }
            )
            
            logger.info(f"Task creation notification sent: {service_request.request_number} -> {task.task_number}")
            
        except Exception as e:
            logger.error(f"Failed to send task creation notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_technician_enroute(service_request, task):
        """
        Send notification when technician is en route.
        """
        try:
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Technician En Route - Request {service_request.request_number}',
                template='service_requests/emails/technician_enroute.html',
                context={
                    'request': service_request,
                    'task': task,
                    'customer_name': service_request.customer.full_name,
                }
            )
            
            logger.info(f"Technician enroute notification sent: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send technician enroute notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_work_completed(service_request, task):
        """
        Send notification when work is completed.
        """
        try:
            RequestNotificationService._send_customer_email(
                to_email=service_request.customer.email,
                subject=f'Work Completed - Request {service_request.request_number}',
                template='service_requests/emails/work_completed.html',
                context={
                    'request': service_request,
                    'task': task,
                    'customer_name': service_request.customer.full_name,
                }
            )
            
            logger.info(f"Work completion notification sent: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send work completion notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def notify_comment_added(service_request, comment):
        """
        Send notification when admin adds a comment.
        """
        try:
            # Only notify customer if comment is not internal
            if not comment.is_internal and comment.user and comment.user != service_request.customer:
                RequestNotificationService._send_customer_email(
                    to_email=service_request.customer.email,
                    subject=f'New Comment on Request {service_request.request_number}',
                    template='service_requests/emails/comment_added.html',
                    context={
                        'request': service_request,
                        'comment': comment,
                        'customer_name': service_request.customer.full_name,
                    }
                )
                
                logger.info(f"Comment notification sent: {service_request.request_number}")
            
        except Exception as e:
            logger.error(f"Failed to send comment notification: {str(e)}", exc_info=True)
    
    @staticmethod
    def _send_customer_email(to_email, subject, template, context):
        """
        Send email to customer.
        """
        try:
            # Render HTML email
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except Exception as e:
            logger.error(f"Failed to send customer email to {to_email}: {str(e)}", exc_info=True)
            # Don't raise - notification failure shouldn't break the main flow
    
    @staticmethod
    def _send_admin_email(to_email, subject, template, context):
        """
        Send email to admin/manager.
        """
        try:
            # Render HTML email
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except Exception as e:
            logger.error(f"Failed to send admin email to {to_email}: {str(e)}", exc_info=True)
            # Don't raise - notification failure shouldn't break the main flow
