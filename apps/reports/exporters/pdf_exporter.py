"""
PDF Report Exporter

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""
import logging
from io import BytesIO
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


class PDFExporter:
    """
    Generate PDF reports using WeasyPrint.
    """
    
    def __init__(self, template_name, context):
        """
        Initialize PDF exporter.
        
        Args:
            template_name: Path to Django template
            context: Context dictionary for template rendering
        """
        self.template_name = template_name
        self.context = context
    
    def generate(self):
        """
        Generate PDF and return bytes.
        
        Returns:
            bytes: PDF file content
        """
        try:
            # Import WeasyPrint here to avoid import errors if not installed
            from weasyprint import HTML, CSS
            
            # Render HTML template
            html_string = render_to_string(self.template_name, self.context)
            
            # Create HTML object and generate PDF
            html_doc = HTML(string=html_string)
            pdf_bytes = html_doc.write_pdf()
            
            logger.info(f"PDF generated successfully from template: {self.template_name}")
            return pdf_bytes
            
        except ImportError as e:
            logger.error(f"WeasyPrint not installed: {str(e)}")
            raise ImportError(
                "WeasyPrint is required for PDF generation. "
                "Install it with: pip install weasyprint"
            )
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}", exc_info=True)
            raise
    
    def generate_to_file(self, filepath):
        """
        Generate PDF and save to file.
        
        Args:
            filepath: Path where PDF should be saved
        """
        pdf_bytes = self.generate()
        
        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)
        
        logger.info(f"PDF saved to: {filepath}")
    
    def generate_to_buffer(self):
        """
        Generate PDF and return as BytesIO buffer.
        
        Returns:
            BytesIO: Buffer containing PDF data
        """
        pdf_bytes = self.generate()
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def get_default_css():
        """
        Get default CSS for PDF styling.
        
        Returns:
            str: CSS string
        """
        return """
        @page {
            size: A4 landscape;
            margin: 1.5cm;
            @top-center {
                content: "Report";
            }
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
            }
        }
        
        body {
            font-family: Arial, sans-serif;
            font-size: 8pt;
            line-height: 1.3;
        }
        
        h1 {
            font-size: 16pt;
            color: #333;
            margin-bottom: 8pt;
        }
        
        h2 {
            font-size: 12pt;
            color: #555;
            margin-top: 12pt;
            margin-bottom: 6pt;
        }
        
        h3 {
            font-size: 10pt;
            color: #666;
            margin-top: 8pt;
            margin-bottom: 4pt;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 8pt 0;
            font-size: 7pt;
        }
        
        th {
            background-color: #f0f0f0;
            padding: 4pt 3pt;
            text-align: left;
            border: 0.5pt solid #ddd;
            font-weight: bold;
            font-size: 7pt;
        }
        
        td {
            padding: 3pt;
            border: 0.5pt solid #ddd;
            font-size: 7pt;
            word-wrap: break-word;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .header {
            text-align: center;
            margin-bottom: 15pt;
        }
        
        .summary-box {
            background-color: #f5f5f5;
            padding: 8pt;
            margin: 8pt 0;
            border-left: 2pt solid #007bff;
        }
        
        .footer {
            margin-top: 15pt;
            padding-top: 8pt;
            border-top: 0.5pt solid #ddd;
            font-size: 7pt;
            color: #666;
        }
        
        small {
            font-size: 6pt;
            color: #666;
        }
        """


def generate_pdf_report(report_data, report_type):
    """
    Convenience function to generate PDF from report data.
    
    Args:
        report_data: Report data dictionary
        report_type: Type of report
        
    Returns:
        bytes: PDF file content
    """
    # Determine template based on report type
    template_map = {
        'task_summary': 'reports/task_summary.html',
        'task_detail': 'reports/task_detail.html',
        'overdue_tasks': 'reports/overdue_tasks.html',
        'equipment_summary': 'reports/equipment_summary.html',
        'equipment_detail': 'reports/equipment_detail.html',
        'equipment_maintenance_history': 'reports/equipment_maintenance.html',
        'equipment_utilization': 'reports/equipment_utilization.html',
        'technician_worksheet': 'reports/technician_worksheet.html',
        'technician_performance': 'reports/technician_performance.html',
        'technician_productivity': 'reports/technician_productivity.html',
        'team_performance': 'reports/team_performance.html',
        'overtime_report': 'reports/overtime_report.html',
        'service_request_summary': 'reports/service_request_summary.html',
        'service_request_detail': 'reports/service_request_detail.html',
        'labor_cost': 'reports/labor_cost.html',
        'materials_usage': 'reports/materials_usage.html',
        'customer_billing': 'reports/customer_billing.html',
    }
    
    template_name = template_map.get(report_type, 'reports/base_report.html')
    
    # Prepare context
    context = {
        'report': report_data,
        'css': PDFExporter.get_default_css(),
    }
    
    # Generate PDF
    exporter = PDFExporter(template_name, context)
    return exporter.generate()
