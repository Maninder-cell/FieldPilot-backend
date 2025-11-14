"""
Reports Celery Tasks

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
import logging
import time

from .models import ReportAuditLog, ReportSchedule
from .registry import registry
from .exporters.pdf_exporter import generate_pdf_report
from .exporters.excel_exporter import generate_excel_report

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_report_async(self, user_id, report_type, filters, output_format='json'):
    """
    Generate a report asynchronously.
    
    Args:
        user_id: ID of user generating the report
        report_type: Type of report to generate
        filters: Filters to apply
        output_format: Output format (json, pdf, excel)
        
    Returns:
        dict: Report data or file path
    """
    from apps.authentication.models import User
    
    try:
        # Get user
        user = User.objects.get(id=user_id)
        
        # Create audit log
        audit_log = ReportAuditLog.log_report_generation(
            user=user,
            report_type=report_type,
            report_name=registry.get_generator_class(report_type).report_name,
            filters=filters,
            format=output_format
        )
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'Generating report...'}
        )
        
        start_time = time.time()
        
        # Generate report
        generator = registry.create_generator(report_type, user, filters)
        report_data = generator.generate(use_cache=False)  # Don't use cache for async
        
        execution_time = time.time() - start_time
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 50, 'total': 100, 'status': 'Report generated, preparing export...'}
        )
        
        # Store report data in cache
        cache_key = f"report_data:{audit_log.id}"
        cache.set(cache_key, report_data, 3600)  # Cache for 1 hour
        
        # Mark audit log as successful
        audit_log.mark_success(execution_time)
        
        # Update progress
        self.update_state(
            state='SUCCESS',
            meta={
                'current': 100,
                'total': 100,
                'status': 'Complete',
                'report_id': str(audit_log.id),
                'report_data': report_data if output_format == 'json' else None
            }
        )
        
        return {
            'report_id': str(audit_log.id),
            'status': 'success',
            'execution_time': execution_time
        }
        
    except Exception as e:
        logger.error(f"Error in async report generation: {str(e)}", exc_info=True)
        
        # Mark audit log as failed if it exists
        try:
            if 'audit_log' in locals():
                audit_log.mark_failed(str(e))
        except:
            pass
        
        # Retry the task
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_pdf_async(self, report_id):
    """
    Generate PDF for a report asynchronously.
    
    Args:
        report_id: ID of the report audit log
        
    Returns:
        dict: File path and status
    """
    try:
        audit_log = ReportAuditLog.objects.get(id=report_id)
        
        # Get report data from cache
        cache_key = f"report_data:{report_id}"
        report_data = cache.get(cache_key)
        
        if not report_data:
            raise ValueError("Report data not found in cache")
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Generating PDF...'}
        )
        
        # Generate PDF
        pdf_bytes = generate_pdf_report(report_data, audit_log.report_type)
        
        # Store PDF in cache
        pdf_cache_key = f"report_pdf:{report_id}"
        cache.set(pdf_cache_key, pdf_bytes, 3600)
        
        self.update_state(
            state='SUCCESS',
            meta={'current': 100, 'total': 100, 'status': 'PDF generated'}
        )
        
        return {
            'report_id': str(report_id),
            'format': 'pdf',
            'status': 'success'
        }
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_excel_async(self, report_id):
    """
    Generate Excel for a report asynchronously.
    
    Args:
        report_id: ID of the report audit log
        
    Returns:
        dict: File path and status
    """
    try:
        audit_log = ReportAuditLog.objects.get(id=report_id)
        
        # Get report data from cache
        cache_key = f"report_data:{report_id}"
        report_data = cache.get(cache_key)
        
        if not report_data:
            raise ValueError("Report data not found in cache")
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 30, 'total': 100, 'status': 'Generating Excel...'}
        )
        
        # Generate Excel
        excel_bytes = generate_excel_report(report_data, audit_log.report_type)
        
        # Store Excel in cache
        excel_cache_key = f"report_excel:{report_id}"
        cache.set(excel_cache_key, excel_bytes, 3600)
        
        self.update_state(
            state='SUCCESS',
            meta={'current': 100, 'total': 100, 'status': 'Excel generated'}
        )
        
        return {
            'report_id': str(report_id),
            'format': 'excel',
            'status': 'success'
        }
        
    except Exception as e:
        logger.error(f"Error generating Excel: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@shared_task
def execute_scheduled_reports():
    """
    Execute all due scheduled reports.
    This task should be run periodically (e.g., every 15 minutes).
    """
    logger.info("Checking for due scheduled reports...")
    
    due_schedules = ReportSchedule.get_due_schedules()
    
    for schedule in due_schedules:
        try:
            logger.info(f"Executing scheduled report: {schedule.name}")
            
            # Generate report
            # Note: We need a system user or the creator for this
            if schedule.created_by:
                user = schedule.created_by
            else:
                # Skip if no user available
                logger.warning(f"No user found for schedule {schedule.name}, skipping")
                continue
            
            generator = registry.create_generator(
                schedule.report_type,
                user,
                schedule.filters
            )
            report_data = generator.generate(use_cache=False)
            
            # Generate file based on format
            if schedule.format == 'pdf':
                file_bytes = generate_pdf_report(report_data, schedule.report_type)
                filename = f"{schedule.report_type}_{timezone.now().strftime('%Y%m%d')}.pdf"
            else:  # excel
                file_bytes = generate_excel_report(report_data, schedule.report_type)
                filename = f"{schedule.report_type}_{timezone.now().strftime('%Y%m%d')}.xlsx"
            
            # Send email with attachment
            send_scheduled_report_email.delay(
                schedule.id,
                schedule.recipients,
                filename,
                file_bytes
            )
            
            # Mark schedule as executed
            schedule.mark_executed()
            
            logger.info(f"Successfully executed scheduled report: {schedule.name}")
            
        except Exception as e:
            logger.error(
                f"Error executing scheduled report {schedule.name}: {str(e)}",
                exc_info=True
            )
            # Continue with next schedule


@shared_task(bind=True, max_retries=3)
def send_scheduled_report_email(self, schedule_id, recipients, filename, file_bytes):
    """
    Send scheduled report via email.
    
    Args:
        schedule_id: ID of the schedule
        recipients: List of email addresses
        filename: Name of the attachment file
        file_bytes: File content as bytes
    """
    try:
        from django.core.mail import EmailMessage
        from django.conf import settings
        
        schedule = ReportSchedule.objects.get(id=schedule_id)
        
        subject = f"Scheduled Report: {schedule.name}"
        body = f"""
        Hello,
        
        Please find attached your scheduled report: {schedule.name}
        
        Report Type: {schedule.report_type}
        Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        This is an automated email from FieldPilot.
        """
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )
        
        # Attach file
        content_type = 'application/pdf' if filename.endswith('.pdf') else \
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        email.attach(filename, file_bytes, content_type)
        
        email.send()
        
        logger.info(f"Sent scheduled report email for: {schedule.name}")
        
    except Exception as e:
        logger.error(f"Error sending scheduled report email: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes
