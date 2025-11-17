"""
DRF Spectacular hooks for multi-tenant support

Copyright (c) 2025 FieldRino. All rights reserved.
This source code is proprietary and confidential.
"""


def postprocessing_hook(result, generator, request, public):
    """
    Postprocessing hook to dynamically set server URL based on the current request.
    This ensures Swagger UI uses the correct tenant subdomain.
    
    Args:
        result: The generated OpenAPI schema dictionary
        generator: The schema generator instance
        request: The current HTTP request
        public: Boolean indicating if this is a public schema
    
    Returns:
        Modified OpenAPI schema with dynamic server URL
    """
    if request:
        # Get the current host from the request
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        server_url = f"{scheme}://{host}"
        
        # Update the servers list with the current host
        result['servers'] = [
            {
                'url': server_url,
                'description': f'Current tenant ({host})'
            }
        ]
    
    return result
