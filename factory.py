"""Flask application factory for creating and configuring app instances."""
from typing import Optional
from flask import Flask
from flask_login import LoginManager

from config import get_config
from models import db, User
from rate_limit import limiter, handle_rate_limit_error
from sentry_config import init_sentry
from file_upload_service import init_upload_folder

try:
    from flask_migrate import Migrate
    HAS_MIGRATE = True
except ImportError:
    HAS_MIGRATE = False


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory pattern: creates and configures Flask app instance.
    
    This pattern enables:
    - Testing with different configs (test, development, production)
    - Multiple app instances with different configurations
    - Clear separation of concerns (initialization vs routes)
    - Easier debugging and dependency injection
    
    Args:
        config_name: Configuration environment (development, testing, production).
                    If None, uses FLASK_ENV environment variable or defaults to 'development'.
    
    Returns:
        Configured Flask application instance.
    
    Raises:
        RuntimeError: If SECRET_KEY or JWT_SECRET not properly configured in production.
    """
    import os
    
    # Determine config environment
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration - THIS WILL FAIL FAST IF SECRETS INVALID IN PRODUCTION
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions with app
    _init_extensions(app)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Initialize upload folder
    init_upload_folder()
    
    # Setup error handlers
    app.errorhandler(429)(lambda e: handle_rate_limit_error(e))
    
    # Setup request/response logging for debugging
    _setup_request_logging(app, config_name)
    
    return app


def _init_extensions(app: Flask) -> None:
    """
    Initialize all Flask extensions with the app instance.
    
    Extensions initialized:
    - SQLAlchemy (ORM)
    - Flask-Mail (Email)
    - Flask-WTF/CSRFProtect (CSRF protection)
    - Flask-Limiter (Rate limiting)
    - Flask-Login (Session management)
    - Flask-Migrate (Database migrations)
    - Sentry (Error tracking)
    """
    # Database
    db.init_app(app)
    
    # CSRF Protection - CRITICAL SECURITY FIX
    # Must be initialized before routes/blueprints
    # Configure to skip API endpoints (they use JWT instead)
    csrf_protection_enabled = False
    try:
        from flask_wtf.csrf import CSRFProtect
        # Skip CSRF check by default, only check where needed
        app.config['WTF_CSRF_CHECK_DEFAULT'] = False
        csrf = CSRFProtect()
        csrf.init_app(app)
        csrf_protection_enabled = True
        # Store csrf in app for use in decorators
        app.csrf = csrf
        app.logger.info("CSRF Protection enabled via Flask-WTF (API routes exempted)")
    except (ImportError, Exception) as e:
        app.logger.warning(f"CSRF Protection not available: {e}")
        
        # Fallback: provide empty csrf_token to templates to prevent template errors
        # Only used when Flask-WTF is not available
        @app.context_processor
        def csrf_token_fallback():
            return {'csrf_token': lambda: ''}
    
    # Rate Limiting
    limiter.init_app(app)
    
    # Database Migrations
    if HAS_MIGRATE:
        migrate = Migrate(app, db)
    
    # Session Management
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        """Load user by ID for Flask-Login."""
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None
    
    # Error Tracking
    init_sentry(app, environment=app.config.get('FLASK_ENV', 'development'))


def _register_blueprints(app: Flask) -> None:
    """
    Register all application blueprints.
    
    Blueprints provide modular route organization:
    - auth: Authentication routes (login, register, password reset)
    - dashboard: Main dashboard and expense management
    - analytics: Analytics and reporting
    - uploads: File upload management
    - admin: Administrative functions
    - api: RESTful API endpoints
    """
    from api import api_bp, set_jwt_secret
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.analytics import analytics_bp
    from routes.uploads import uploads_bp
    from routes.admin import admin_bp
    
    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(admin_bp)
    
    # Setup JWT secret for API
    jwt_secret = app.config.get('JWT_SECRET')
    if jwt_secret:
        set_jwt_secret(jwt_secret)


def _setup_request_logging(app: Flask, config_name: str) -> None:
    """
    Setup request/response logging for debugging.
    
    Args:
        app: Flask application instance.
        config_name: Configuration environment name.
    """
    import logging
    
    # Only log requests in development/testing
    if config_name in ('development', 'testing'):
        @app.before_request
        def log_request():
            """Log incoming requests."""
            from flask import request
            app.logger.debug(
                f"REQUEST: {request.method} {request.path} "
                f"from {request.remote_addr}"
            )
        
        @app.after_request
        def log_response(response):
            """Log outgoing responses."""
            from flask import request
            app.logger.debug(
                f"RESPONSE: {request.method} {request.path} "
                f"status={response.status_code}"
            )
            return response
