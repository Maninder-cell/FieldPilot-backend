"""
Reports Views

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.http import HttpResponse
from django.core.cache import cache
import logging
import time

from apps.core.responses import success_response, error_response
from .permissions import IsAdminOrManager
from .models import ReportAuditLog, ReportSchedule
from .serializers import (
    GenerateReportSerializer, ReportDataSerializer, ReportAuditLogSerializer,
    ReportScheduleSerializer, CreateReportScheduleSerializer, UpdateReportScheduleSerializer,
    ReportTypeSerializer, ReportTypeDetailSerializer
)
from .registry import registry, list_reports, get_report_info
from .exporters.pdf_exporter import generate_pdf_report
from .exporters.excel_exporter import generate_excel_report

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Reports'],
    summary='Generate a report',
    description='Generate a report with specified filters and format',
    request=GenerateReportSerializer,
    responses={200: ReportDataSerializer}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def generate_report(request):
    """Generate a report."""
    serializer = GenerateReportSerializer(data=request.data)
    
    if not serializer.is_valid():
        return error_response(
            message='Invalid request data',
            details=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    report_type = serializer.validated_data['report_type']
    filters = serializer.validated_data.get('filters', {})
    output_format = serializer.validated_data.get('format', 'json')
    use_cache = serializer.validated_data.get('use_cache', True)
    
    # Create audit log
    audit_log = ReportAuditLog.log_report_generation(
        user=request.user,
        report_type=report_type,
        report_name=registry.get_generator_class(report_type).report_name,
        filters=filters,
        format=output_format
    )
    
    try:
        start_time = time.time()
        
        # Generate report
        generator = registry.create_generator(report_type, request.user, filters)
        report_data = generator.generate(use_cache=use_cache)
        
        execution_time = time.time() - start_time
        
        # Mark audit log as successful
        audit_log.mark_success(execution_time)
        
        # Return JSON data
        if output_format == 'json':
            return success_response(data=report_data)
        
        # For PDF/Excel, store report_id in cache for later export
        cache_key = f"report_data:{audit_log.id}"
        cache.set(cache_key, report_data, 3600)  # Cache for 1 hour
        
        return success_response(
            data={
                'report_id': str(audit_log.id),
                'message': f'Report generated successfully. Use report_id to export as {output_format}.',
                'export_url': f'/api/v1/reports/{audit_log.id}/export/{output_format}/'
            }
        )
        
    except ValueError as e:
        audit_log.mark_failed(str(e))
        return error_response(
            message='Invalid filter values',
            details={'filters': str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        audit_log.mark_failed(str(e))
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to generate report',
            details={'detail': str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Reports'],
    summary='Get report details',
    description='Get details of a previously generated report'
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def report_detail(request, report_id):
    """Get report details."""
    try:
        audit_log = ReportAuditLog.objects.get(id=report_id)
        
        # Check if report data is still cached
        cache_key = f"report_data:{report_id}"
        report_data = cache.get(cache_key)
        
        if report_data:
            return success_response(data=report_data)
        else:
            return error_response(
                message='Report data expired. Please regenerate the report.',
                status_code=status.HTTP_404_NOT_FOUND
            )
    except ReportAuditLog.DoesNotExist:
        return error_response(
            message='Report not found',
            status_code=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    tags=['Reports'],
    summary='Export report as PDF',
    description='Export a generated report as PDF file'
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def export_pdf(request, report_id):
    """Export report as PDF."""
    try:
        audit_log = ReportAuditLog.objects.get(id=report_id)
        
        # Get report data from cache
        cache_key = f"report_data:{report_id}"
        report_data = cache.get(cache_key)
        
        if not report_data:
            return error_response(
                message='Report data expired. Please regenerate the report.',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Generate PDF
        pdf_bytes = generate_pdf_report(report_data, audit_log.report_type)
        
        # Create response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"{audit_log.report_type}_{report_id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except ReportAuditLog.DoesNotExist:
        return error_response(
            message='Report not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error exporting PDF: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to export PDF',
            details={'detail': str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Reports'],
    summary='Export report as Excel',
    description='Export a generated report as Excel file'
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def export_excel(request, report_id):
    """Export report as Excel."""
    try:
        audit_log = ReportAuditLog.objects.get(id=report_id)
        
        # Get report data from cache
        cache_key = f"report_data:{report_id}"
        report_data = cache.get(cache_key)
        
        if not report_data:
            return error_response(
                message='Report data expired. Please regenerate the report.',
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Generate Excel
        excel_bytes = generate_excel_report(report_data, audit_log.report_type)
        
        # Create response
        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"{audit_log.report_type}_{report_id}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except ReportAuditLog.DoesNotExist:
        return error_response(
            message='Report not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error exporting Excel: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to export Excel',
            details={'detail': str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Reports'],
    summary='List available report types',
    description='Get list of all available report types',
    responses={200: ReportTypeSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def report_types_list(request):
    """List available report types."""
    try:
        report_types = list_reports()
        serializer = ReportTypeSerializer(report_types, many=True)
        return success_response(data=serializer.data)
    except Exception as e:
        logger.error(f"Error listing report types: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to list report types',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Reports'],
    summary='Get report type details',
    description='Get detailed information about a specific report type',
    responses={200: ReportTypeDetailSerializer}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def report_type_detail(request, report_type):
    """Get report type details."""
    try:
        report_info = get_report_info(report_type)
        serializer = ReportTypeDetailSerializer(report_info)
        return success_response(data=serializer.data)
    except KeyError:
        return error_response(
            message=f'Unknown report type: {report_type}',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error getting report type details: {str(e)}", exc_info=True)
        return error_response(
            message='Failed to get report type details',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Reports'],
    summary='List or create report schedules',
    description='Get list of report schedules or create a new schedule',
    request=CreateReportScheduleSerializer,
    responses={200: ReportScheduleSerializer(many=True), 201: ReportScheduleSerializer}
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def schedule_list_create(request):
    """List or create report schedules."""
    if request.method == 'GET':
        queryset = ReportSchedule.objects.all()
        
        # Apply filters
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        report_type = request.query_params.get('report_type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = ReportScheduleSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ReportScheduleSerializer(queryset, many=True)
        return success_response(data=serializer.data)
    
    elif request.method == 'POST':
        serializer = CreateReportScheduleSerializer(data=request.data)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid schedule data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        schedule = serializer.save(created_by=request.user, updated_by=request.user)
        
        response_serializer = ReportScheduleSerializer(schedule)
        return success_response(
            data=response_serializer.data,
            message='Report schedule created successfully',
            status_code=status.HTTP_201_CREATED
        )


@extend_schema(
    tags=['Reports'],
    summary='Get, update, or delete report schedule',
    description='Manage a specific report schedule',
    request=UpdateReportScheduleSerializer,
    responses={200: ReportScheduleSerializer}
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def schedule_detail(request, schedule_id):
    """Get, update, or delete report schedule."""
    try:
        schedule = ReportSchedule.objects.get(id=schedule_id)
    except ReportSchedule.DoesNotExist:
        return error_response(
            message='Schedule not found',
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = ReportScheduleSerializer(schedule)
        return success_response(data=serializer.data)
    
    elif request.method == 'PUT':
        serializer = UpdateReportScheduleSerializer(schedule, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                message='Invalid schedule data',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        schedule = serializer.save(updated_by=request.user)
        
        response_serializer = ReportScheduleSerializer(schedule)
        return success_response(
            data=response_serializer.data,
            message='Report schedule updated successfully'
        )
    
    elif request.method == 'DELETE':
        schedule.delete()
        return success_response(
            message='Report schedule deleted successfully',
            status_code=status.HTTP_204_NO_CONTENT
        )


@extend_schema(
    tags=['Reports'],
    summary='List report audit logs',
    description='Get list of report generation history',
    parameters=[
        OpenApiParameter('page', int, description='Page number'),
        OpenApiParameter('page_size', int, description='Items per page'),
        OpenApiParameter('report_type', str, description='Filter by report type'),
        OpenApiParameter('status', str, description='Filter by status'),
    ],
    responses={200: ReportAuditLogSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrManager])
def audit_list(request):
    """List report audit logs."""
    queryset = ReportAuditLog.objects.all()
    
    # Apply filters
    report_type = request.query_params.get('report_type')
    if report_type:
        queryset = queryset.filter(report_type=report_type)
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    user_id = request.query_params.get('user')
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    
    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = int(request.query_params.get('page_size', 50))
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        serializer = ReportAuditLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    serializer = ReportAuditLogSerializer(queryset, many=True)
    return success_response(data=serializer.data)
