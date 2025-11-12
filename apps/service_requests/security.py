"""
Service Request Security Utilities

Copyright (c) 2025 FieldPilot. All rights reserved.
This source code is proprietary and confidential.
"""
import hashlib
import time
from django.conf import settings
from django.core.signing import Signer, BadSignature
import logging

logger = logging.getLogger(__name__)


class FileSecurityValidator:
    """
    Security utilities for file uploads.
    Task 19.1: File upload security
    """
    
    # Allowed MIME types (whitelist)
    ALLOWED_MIME_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/gif',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.gif',
        '.pdf', '.doc', '.docx'
    ]
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    @staticmethod
    def validate_file_type(file):
        """
        Validate file type against whitelist.
        """
        content_type = file.content_type
        
        if content_type not in FileSecurityValidator.ALLOWED_MIME_TYPES:
            return False, f'File type {content_type} is not allowed'
        
        # Check file extension
        file_name = file.name.lower()
        if not any(file_name.endswith(ext) for ext in FileSecurityValidator.ALLOWED_EXTENSIONS):
            return False, 'File extension is not allowed'
        
        return True, None
    
    @staticmethod
    def validate_file_size(file):
        """
        Validate file size.
        """
        if file.size > FileSecurityValidator.MAX_FILE_SIZE:
            max_mb = FileSecurityValidator.MAX_FILE_SIZE / (1024 * 1024)
            return False, f'File size exceeds maximum of {max_mb}MB'
        
        return True, None
    
    @staticmethod
    def scan_file_for_malware(file):
        """
        Scan file for malware.
        
        Note: This is a placeholder. In production, integrate with:
        - ClamAV
        - VirusTotal API
        - AWS S3 virus scanning
        - Or other antivirus service
        """
        # TODO: Implement actual virus scanning
        # For now, just log that scanning should be done
        logger.info(f"File scan requested for: {file.name}")
        
        # In production, you would:
        # 1. Save file to temporary location
        # 2. Run virus scanner
        # 3. Delete temp file
        # 4. Return scan results
        
        return True, None
    
    @staticmethod
    def validate_file(file):
        """
        Complete file validation.
        """
        # Validate file type
        valid, error = FileSecurityValidator.validate_file_type(file)
        if not valid:
            return False, error
        
        # Validate file size
        valid, error = FileSecurityValidator.validate_file_size(file)
        if not valid:
            return False, error
        
        # Scan for malware
        valid, error = FileSecurityValidator.scan_file_for_malware(file)
        if not valid:
            return False, error
        
        return True, None


class SecureURLGenerator:
    """
    Generate secure signed URLs for file downloads.
    Task 19.1: Generate secure signed URLs
    """
    
    @staticmethod
    def generate_signed_url(file_path, expiry_seconds=3600):
        """
        Generate a signed URL for secure file access.
        
        Args:
            file_path: Path to the file
            expiry_seconds: URL expiry time in seconds (default 1 hour)
        
        Returns:
            Signed URL string
        """
        signer = Signer()
        
        # Create payload with file path and expiry timestamp
        expiry_time = int(time.time()) + expiry_seconds
        payload = f"{file_path}:{expiry_time}"
        
        # Sign the payload
        signed_payload = signer.sign(payload)
        
        return signed_payload
    
    @staticmethod
    def verify_signed_url(signed_url):
        """
        Verify a signed URL and check if it's expired.
        
        Args:
            signed_url: The signed URL to verify
        
        Returns:
            (valid, file_path) tuple
        """
        signer = Signer()
        
        try:
            # Unsign the payload
            payload = signer.unsign(signed_url)
            
            # Extract file path and expiry time
            file_path, expiry_time = payload.rsplit(':', 1)
            expiry_time = int(expiry_time)
            
            # Check if expired
            if time.time() > expiry_time:
                return False, None
            
            return True, file_path
            
        except (BadSignature, ValueError) as e:
            logger.warning(f"Invalid signed URL: {str(e)}")
            return False, None


class InputSanitizer:
    """
    Sanitize user input to prevent injection attacks.
    Task 19.2: Input validation and sanitization
    """
    
    @staticmethod
    def sanitize_string(value, max_length=None):
        """
        Sanitize string input.
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Strip leading/trailing whitespace
        value = value.strip()
        
        # Limit length if specified
        if max_length and len(value) > max_length:
            value = value[:max_length]
        
        return value
    
    @staticmethod
    def sanitize_html(value):
        """
        Sanitize HTML input to prevent XSS.
        """
        # Remove potentially dangerous HTML tags
        dangerous_tags = [
            '<script', '</script>',
            '<iframe', '</iframe>',
            '<object', '</object>',
            '<embed', '</embed>',
            'javascript:',
            'onerror=',
            'onload=',
        ]
        
        value_lower = value.lower()
        for tag in dangerous_tags:
            if tag in value_lower:
                # Replace with safe version
                value = value.replace(tag, '')
        
        return value


class RateLimiter:
    """
    Rate limiting utilities.
    Task 19.2: Rate limiting
    """
    
    # Rate limits (requests per minute)
    RATE_LIMITS = {
        'customer': 60,  # 60 requests per minute
        'admin': 120,    # 120 requests per minute
        'manager': 120,  # 120 requests per minute
    }
    
    @staticmethod
    def get_rate_limit(user):
        """
        Get rate limit for user based on role.
        """
        if not user or not user.is_authenticated:
            return 30  # Anonymous users: 30 requests per minute
        
        return RateLimiter.RATE_LIMITS.get(user.role, 60)
    
    @staticmethod
    def get_cache_key(user, endpoint):
        """
        Get cache key for rate limiting.
        """
        if user and user.is_authenticated:
            return f"rate_limit:{user.id}:{endpoint}"
        else:
            return f"rate_limit:anonymous:{endpoint}"
