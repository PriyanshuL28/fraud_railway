# fraud_detector/middleware/security.py
# Enhanced security middleware for Railway deployment

import re
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from django.urls import reverse
from django.shortcuts import redirect

class RailwaySecurityMiddleware:
    """
    Advanced security middleware to protect source code and sensitive data
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Patterns that should be blocked
        self.blocked_patterns = [
            r'\.py$', r'\.pyc$', r'\.pyo$',  # Python files
            r'\.env', r'\.git', r'\.sqlite',  # Sensitive files
            r'__pycache__', r'migrations/',    # Directories
            r'\.log$', r'\.sql$', r'\.db$',   # Log and database files
            r'settings\.py', r'wsgi\.py',      # Specific files
            r'manage\.py', r'requirements\.txt',
            r'\.\./', r'\.\.\\',              # Path traversal
            r'~', r'\$',                       # Backup files
        ]
        
        # Compile regex patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) 
                                 for pattern in self.blocked_patterns]
        
        # API endpoints that should be protected
        self.protected_api_patterns = [
            r'/api/internal/',
            r'/debug/',
            r'/__debug__/',
        ]

    def __call__(self, request):
        # Get the requested path
        path = request.path_info
        
        # Check for blocked patterns
        for pattern in self.compiled_patterns:
            if pattern.search(path):
                # Log the attempt (optional)
                if settings.DEBUG:
                    print(f"Blocked access attempt: {path}")
                raise Http404("Page not found")
        
        # Block direct access to media uploads
        if path.startswith('/media/uploads/') and not request.user.is_authenticated:
            return HttpResponseForbidden("Access denied")
        
        # Prevent information disclosure through error messages
        if not settings.DEBUG:
            # Remove sensitive headers from response
            response = self.get_response(request)
            response['Server'] = 'Railway'  # Hide server info
            
            # Remove Django version header
            if 'X-Powered-By' in response:
                del response['X-Powered-By']
                
            return response
        
        return self.get_response(request)

class AdminAccessMiddleware:
    """
    Additional protection for admin panel
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_url = getattr(settings, 'ADMIN_URL', 'admin')
        
    def __call__(self, request):
        # Redirect default admin URL to 404
        if request.path.startswith('/admin/') and self.admin_url != 'admin':
            raise Http404("Page not found")
        
        response = self.get_response(request)
        return response