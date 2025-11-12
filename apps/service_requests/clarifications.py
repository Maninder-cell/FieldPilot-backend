"""
Service Requests Clarification System

Task 10.2: Clarification request feature
Allows admins to request additional information from customers.

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from django.utils import timezone
from django.db import transaction
import logging

from .models import ServiceRequest, RequestAction, RequestComment

logger = logging.getLogger(__name__)


class ClarificationManager:
    """
    Manages clarification requests for service requests.
    Admins can request more information from customers.
    """
    
    @staticmethod
    def request_clarification(service_request, requested_by, clarification_message):
        """
        Request clarification from customer.
        
        Args:
            service_request: ServiceRequest instance
            requested_by: User who is requesting clarification (admin/manager)
            clarification_message: Message asking for clarification
        
        Returns:
            RequestComment: The clarification comment created
        """
        try:
            with transaction.atomic():
                # Create a comment with clarification flag
                comment = RequestComment.objects.create(
                    request=service_request,
                    user=requested_by,
                    comment_text=f"[CLARIFICATION REQUESTED]\n\n{clarification_message}",
                    is_internal=False,  # Visible to customer
                )
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='updated',
                    user=requested_by,
                    description=f'Clarification requested by {requested_by.full_name}',
                    metadata={
                        'clarification_message': clarification_message,
                        'comment_id': str(comment.id),
                    }
                )
                
                # TODO: Send notification to customer
                
                logger.info(
                    f"Clarification requested for service request {service_request.request_number} "
                    f"by {requested_by.full_name}"
                )
                
                return comment
                
        except Exception as e:
            logger.error(
                f"Error requesting clarification: {str(e)}",
                exc_info=True
            )
            raise
    
    @staticmethod
    def respond_to_clarification(service_request, customer, response_message):
        """
        Customer responds to clarification request.
        
        Args:
            service_request: ServiceRequest instance
            customer: Customer user responding
            response_message: Customer's response
        
        Returns:
            RequestComment: The response comment created
        """
        try:
            with transaction.atomic():
                # Create a comment with response
                comment = RequestComment.objects.create(
                    request=service_request,
                    user=customer,
                    comment_text=f"[CLARIFICATION RESPONSE]\n\n{response_message}",
                    is_internal=False,
                )
                
                # Log action
                RequestAction.log_action(
                    request=service_request,
                    action_type='updated',
                    user=customer,
                    description=f'Clarification response provided by {customer.full_name}',
                    metadata={
                        'response_message': response_message,
                        'comment_id': str(comment.id),
                    }
                )
                
                # TODO: Send notification to admin who requested clarification
                
                logger.info(
                    f"Clarification response provided for service request {service_request.request_number} "
                    f"by {customer.full_name}"
                )
                
                return comment
                
        except Exception as e:
            logger.error(
                f"Error responding to clarification: {str(e)}",
                exc_info=True
            )
            raise
    
    @staticmethod
    def get_pending_clarifications(service_request):
        """
        Get all pending clarification requests for a service request.
        
        Args:
            service_request: ServiceRequest instance
        
        Returns:
            list: List of clarification comments
        """
        # Get comments that contain clarification requests
        clarification_comments = service_request.comments.filter(
            comment_text__contains='[CLARIFICATION REQUESTED]',
            is_internal=False
        ).order_by('-created_at')
        
        return clarification_comments
    
    @staticmethod
    def has_pending_clarifications(service_request):
        """
        Check if service request has pending clarifications.
        
        Args:
            service_request: ServiceRequest instance
        
        Returns:
            bool: True if there are pending clarifications
        """
        return ClarificationManager.get_pending_clarifications(service_request).exists()
