"""
Customer Invitation Email Service

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import logging
from django.conf import settings
from apps.core.email_utils import send_template_email

logger = logging.getLogger(__name__)


def send_customer_invitation_email(invitation, frontend_url=None):
    """
    Send invitation email to customer.
    
    Args:
        invitation: CustomerInvitation instance
        frontend_url: Frontend URL for invitation acceptance (optional)
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Calculate days until expiry
        from django.utils import timezone
        days_until_expiry = (invitation.expires_at - timezone.now()).days
        
        # Build invitation URL - same pattern as technician invitations
        if frontend_url:
            invitation_url = f"{frontend_url}/invitations/accept/customer/{invitation.token}"
        else:
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            invitation_url = f"{frontend_url}/invitations/accept/customer/{invitation.token}"
        
        # Prepare email context
        context = {
            'customer_name': invitation.customer.name,
            'inviter_name': invitation.invited_by.full_name if invitation.invited_by else 'FieldPilot Team',
            'company_name': invitation.customer.company_name or 'FieldPilot',
            'invitation_url': invitation_url,
            'invitation_token': invitation.token,
            'expiry_days': max(1, days_until_expiry),
            'email': invitation.email
        }
        
        # Send email using template
        return send_template_email(
            subject=f"You're Invited to {context['company_name']} Customer Portal",
            template_name='customer/invitation',
            context=context,
            recipient_list=[invitation.email],
            fail_silently=False
        )
        
    except Exception as e:
        logger.error(f"Failed to send customer invitation email to {invitation.email}: {str(e)}", exc_info=True)
        return False
