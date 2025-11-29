"""
Email Utilities

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_template_email(
    subject,
    template_name,
    context,
    recipient_list,
    from_email=None,
    fail_silently=False
):
    """
    Send email using HTML and text templates.
    
    Args:
        subject: Email subject
        template_name: Template name without extension (e.g., 'auth/email_verification')
        context: Template context dictionary
        recipient_list: List of recipient email addresses
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
        fail_silently: Whether to suppress exceptions
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Add email to context for footer
        if recipient_list:
            context['email'] = recipient_list[0]
        
        # Render HTML template
        html_template = f'emails/{template_name}.html'
        html_content = render_to_string(html_template, context)
        
        # Render text template (fallback)
        try:
            text_template = f'emails/{template_name}.txt'
            text_content = render_to_string(text_template, context)
        except Exception:
            # If text template doesn't exist, create simple text version
            text_content = f"{subject}\n\n{context.get('message', '')}"
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=fail_silently)
        
        logger.info(f"Email sent successfully to {recipient_list}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {str(e)}", exc_info=True)
        if not fail_silently:
            raise
        return False


def send_otp_email(user, purpose):
    """
    Send OTP email to user for verification or password reset.
    
    Args:
        user: User instance
        purpose: 'email_verification' or 'password_reset'
    
    Returns:
        bool: True if email sent successfully
    """
    subject_map = {
        'email_verification': 'Verify Your Email - FieldRino',
        'password_reset': 'Password Reset Code - FieldRino'
    }
    
    template_map = {
        'email_verification': 'auth/email_verification',
        'password_reset': 'auth/password_reset'
    }
    
    context = {
        'first_name': user.first_name,
        'otp_code': user.otp_code,
        'email': user.email
    }
    
    return send_template_email(
        subject=subject_map.get(purpose, 'OTP Code - FieldRino'),
        template_name=template_map.get(purpose, 'auth/email_verification'),
        context=context,
        recipient_list=[user.email],
        fail_silently=False
    )


def send_welcome_email(user, dashboard_url=None):
    """
    Send welcome email after successful email verification.
    
    Args:
        user: User instance
        dashboard_url: URL to dashboard (optional)
    
    Returns:
        bool: True if email sent successfully
    """
    context = {
        'first_name': user.first_name,
        'email': user.email,
        'dashboard_url': dashboard_url or settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else '#'
    }
    
    return send_template_email(
        subject='Welcome to FieldRino! 🎉',
        template_name='auth/welcome',
        context=context,
        recipient_list=[user.email],
        fail_silently=True
    )


def send_team_invitation_email(invitation, frontend_url=None):
    """
    Send team invitation email.
    
    Args:
        invitation: TenantInvitation instance
        frontend_url: Frontend URL for invitation acceptance (optional)
    
    Returns:
        bool: True if email sent successfully
    """
    # Calculate days until expiry
    from django.utils import timezone
    days_until_expiry = (invitation.expires_at - timezone.now()).days
    
    # Build invitation URL
    if frontend_url:
        invitation_url = f"{frontend_url}/accept-invitation/{invitation.token}"
    else:
        invitation_url = f"http://localhost:3000/accept-invitation/{invitation.token}"
    
    context = {
        'invitee_name': invitation.email.split('@')[0].title(),  # Extract name from email
        'inviter_name': invitation.invited_by.full_name if invitation.invited_by else 'Team Admin',
        'company_name': invitation.tenant.name,
        'role': invitation.role,
        'invitation_url': invitation_url,
        'invitation_token': invitation.token,  # Full token
        'expiry_days': max(1, days_until_expiry),  # At least 1 day
        'email': invitation.email
    }
    
    return send_template_email(
        subject=f"You're Invited to Join {invitation.tenant.name} on FieldRino",
        template_name='team/invitation',
        context=context,
        recipient_list=[invitation.email],
        fail_silently=False
    )


def send_service_request_email(request, customer, email_type='created'):
    """
    Send service request notification email.
    
    Args:
        request: ServiceRequest instance
        customer: Customer instance
        email_type: 'created' or 'accepted'
    
    Returns:
        bool: True if email sent successfully
    """
    subject_map = {
        'created': f'Service Request Received - {request.request_number}',
        'accepted': f'Service Request Accepted - {request.request_number}'
    }
    
    template_map = {
        'created': 'service_requests/request_created',
        'accepted': 'service_requests/request_accepted'
    }
    
    context = {
        'customer_name': customer.full_name if hasattr(customer, 'full_name') else customer.name,
        'request': request,
        'email': customer.email,
        'portal_url': '#'  # Add actual portal URL
    }
    
    # Add extra context for accepted emails
    if email_type == 'accepted':
        context.update({
            'estimated_timeline': getattr(request, 'estimated_timeline', None),
            'response_message': getattr(request, 'response_message', None),
            'assigned_technician': getattr(request, 'assigned_technician', None)
        })
    
    return send_template_email(
        subject=subject_map.get(email_type),
        template_name=template_map.get(email_type),
        context=context,
        recipient_list=[customer.email],
        fail_silently=True
    )


def send_task_assignment_email(task, technician, assigned_by):
    """
    Send task assignment notification email.
    
    Args:
        task: Task instance
        technician: User instance (technician)
        assigned_by: User instance (who assigned the task)
    
    Returns:
        bool: True if email sent successfully
    """
    context = {
        'technician_name': technician.first_name,
        'task': task,
        'assigned_by': assigned_by.full_name,
        'email': technician.email,
        'task_url': '#'  # Add actual task URL
    }
    
    return send_template_email(
        subject=f'New Task Assigned - {task.title}',
        template_name='tasks/task_assigned',
        context=context,
        recipient_list=[technician.email],
        fail_silently=True
    )
