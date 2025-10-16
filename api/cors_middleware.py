from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class CustomCorsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Handle preflight requests
        if request.method == 'OPTIONS':
            response = JsonResponse({})
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken, X-User-ID'
            response['Access-Control-Max-Age'] = '86400'
            return response
        return None

    def process_response(self, request, response):
        # Add CORS headers to all responses
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken, X-User-ID'
        response['Access-Control-Allow-Credentials'] = 'true'
        
        # Log CORS issues for debugging
        if hasattr(request, 'META'):
            origin = request.META.get('HTTP_ORIGIN', 'No Origin')
            logger.info(f"CORS request from origin: {origin}")
        
        return response
