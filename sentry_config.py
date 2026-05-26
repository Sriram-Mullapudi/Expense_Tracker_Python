"""Sentry error tracking configuration."""
import os
import logging
from typing import Optional

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


def init_sentry(app, environment: str = 'production') -> None:
    """
    Initialize Sentry error tracking for the application.
    
    Configures Sentry to capture exceptions, performance data, and breadcrumbs.
    Only initializes if SENTRY_DSN environment variable is set.
    
    Args:
        app: Flask application instance
        environment: Deployment environment ('development', 'staging', 'production')
    
    Environment Variables:
        SENTRY_DSN: Sentry project DSN (required to enable Sentry)
        RELEASE: Application version/release (optional)
    """
    if not SENTRY_AVAILABLE:
        logging.warning("Sentry SDK not installed. Error tracking disabled. Install with: pip install sentry-sdk")
        return
    
    sentry_dsn: Optional[str] = os.getenv('SENTRY_DSN')
    
    if not sentry_dsn:
        logging.info("SENTRY_DSN not configured. Error tracking disabled.")
        return
    
    try:
        release = os.getenv('RELEASE', 'unknown')
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(),
                SqlalchemyIntegration(),
            ],
            # Set tracesSampleRate to 1.0 to capture 100% of transactions for performance monitoring.
            # We recommend adjusting this value in production:
            # - Development: 1.0 (capture all)
            # - Staging: 0.5-0.9 (sample most transactions)
            # - Production: 0.1-0.3 (sample fewer transactions to reduce overhead)
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            
            # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
            # We recommend adjusting this value in production:
            profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),
            
            # Enable SDK debug mode (helpful during setup)
            debug=os.getenv('SENTRY_DEBUG', 'False').lower() == 'true',
            
            # Release version
            release=release,
            
            # Environment
            environment=environment,
            
            # Attach stack traces
            attach_stacktrace=True,
            
            # Include local variables in stack traces (careful with sensitive data in production!)
            include_local_variables=environment != 'production',
            
            # Maximum breadcrumb count
            max_breadcrumbs=100,
            
            # Before sending event to Sentry (opportunity to filter/modify)
            before_send=_before_send_filter,
            
            # Custom client options
            server_name=os.getenv('APP_URL', 'localhost'),
        )
        
        # Set user context when available
        with app.app_context():
            from flask_login import current_user
            
            @app.before_request
            def set_sentry_user() -> None:
                """Set Sentry user context for authenticated requests."""
                try:
                    if current_user and current_user.is_authenticated:
                        sentry_sdk.set_user({
                            'id': current_user.id,
                            'username': current_user.username,
                            'email': current_user.email,
                            'ip_address': '{{auto}}'
                        })
                except Exception:
                    pass  # current_user may not be available in all contexts
        
        logging.info(f"Sentry initialized successfully. Environment: {environment}, Release: {release}")
        
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {str(e)}")


def _before_send_filter(event, hint) -> Optional[dict]:
    """
    Filter events before sending to Sentry.
    
    Removes potentially sensitive information and filters out non-critical errors.
    
    Args:
        event: Sentry event dict
        hint: Dict with exception information
    
    Returns:
        Modified event dict or None to drop the event
    """
    # Drop 404 errors (not helpful for debugging)
    if event.get('tags', {}).get('status_code') == 404:
        return None
    
    # Drop 400 errors from form validation (expected)
    if event.get('tags', {}).get('status_code') == 400:
        exception = hint.get('exc_info')
        if exception and 'validation' in str(exception[1]).lower():
            return None
    
    # Remove potentially sensitive headers
    if 'request' in event:
        headers = event['request'].get('headers', {})
        sensitive_headers = ['Authorization', 'Cookie', 'X-API-Key', 'X-Auth-Token']
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '[REDACTED]'
    
    # Remove request body if it might contain sensitive data
    if 'request' in event:
        body = event['request'].get('data', '')
        if body and any(s in body.lower() for s in ['password', 'token', 'secret', 'key']):
            event['request']['data'] = '[REDACTED]'
    
    return event


def capture_exception(exception: Exception, context: Optional[dict] = None) -> None:
    """
    Manually capture an exception in Sentry.
    
    Args:
        exception: Exception to capture
        context: Optional additional context (key-value pairs)
    """
    if not SENTRY_AVAILABLE:
        return
    
    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(exception)
    except Exception as e:
        logging.error(f"Failed to capture exception in Sentry: {str(e)}")


def capture_message(message: str, level: str = 'info', context: Optional[dict] = None) -> None:
    """
    Manually capture a message in Sentry.
    
    Args:
        message: Message to capture
        level: Log level ('debug', 'info', 'warning', 'error', 'fatal')
        context: Optional additional context
    """
    if not SENTRY_AVAILABLE:
        return
    
    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)
    except Exception as e:
        logging.error(f"Failed to capture message in Sentry: {str(e)}")


def set_user_context(user_id: int, username: str = '', email: str = '') -> None:
    """
    Set user context for Sentry events.
    
    Args:
        user_id: User ID
        username: Username (optional)
        email: Email address (optional)
    """
    if not SENTRY_AVAILABLE:
        return
    
    try:
        sentry_sdk.set_user({
            'id': user_id,
            'username': username,
            'email': email,
            'ip_address': '{{auto}}'
        })
    except Exception as e:
        logging.error(f"Failed to set user context in Sentry: {str(e)}")


def clear_user_context() -> None:
    """Clear user context (e.g., on logout)."""
    if not SENTRY_AVAILABLE:
        return
    
    try:
        sentry_sdk.set_user(None)
    except Exception as e:
        logging.error(f"Failed to clear user context in Sentry: {str(e)}")


def add_breadcrumb(message: str, category: str = 'user-action', level: str = 'info', data: Optional[dict] = None) -> None:
    """
    Add a breadcrumb to Sentry for context-tracking.
    
    Breadcrumbs help track user actions leading up to an error.
    
    Args:
        message: Breadcrumb message
        category: Category (e.g., 'user-action', 'database', 'http')
        level: Log level ('debug', 'info', 'warning', 'error')
        data: Optional additional data
    """
    if not SENTRY_AVAILABLE:
        return
    
    try:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
    except Exception as e:
        logging.error(f"Failed to add breadcrumb to Sentry: {str(e)}")
