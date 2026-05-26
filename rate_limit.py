"""Rate limiting configuration for Flask-Limiter.

Provides centralized rate limiting rules for the application with
memory-based storage (for development) and Redis (for production).

Example usage:
    from rate_limit import limiter
    
    @app.route('/login', methods=['POST'])
    @limiter.limit("5 per minute")
    def login():
        # Max 5 login attempts per minute per IP
        ...
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
from flask import jsonify
import os

# Initialize limiter with memory storage (use Redis in production)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Use Redis in production: "redis://localhost:6379"
)

# Rate limiting tiers:
# Tier 1: Authentication endpoints (login, register) - STRICT
TIER_AUTH_STRICT = "5 per minute;20 per hour"

# Tier 2: Auth verification (forgot password, reset) - MODERATE  
TIER_AUTH_VERIFY = "10 per minute;50 per hour"

# Tier 3: API endpoints (expense CRUD) - STANDARD
TIER_API_STANDARD = "100 per minute;1000 per hour"

# Tier 4: Read-only (dashboard, analytics) - PERMISSIVE
TIER_API_READ = "200 per minute;5000 per hour"

# Tier 5: Unrestricted (health check, public)
TIER_PUBLIC = None


def handle_rate_limit_error(e: RateLimitExceeded):
    """Handle rate limit exceeded errors gracefully.
    
    Args:
        e: RateLimitExceeded exception
    
    Returns:
        JSON response with retry information
    """
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.',
        'retry_after': e.get_retry_after()
    }), 429


__all__ = [
    'limiter',
    'TIER_AUTH_STRICT',
    'TIER_AUTH_VERIFY', 
    'TIER_API_STANDARD',
    'TIER_API_READ',
    'TIER_PUBLIC',
    'handle_rate_limit_error',
]
