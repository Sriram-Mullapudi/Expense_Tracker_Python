"""Application configuration for different environments."""
import os
from datetime import timedelta


class Config:
    """Base configuration with fail-fast pattern for required secrets."""
    
    # Fail-fast: In production, these MUST be set or app won't start
    _env = os.getenv('FLASK_ENV', 'development')
    
    # Only use defaults in development/testing
    if _env in ('development', 'testing'):
        SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
        JWT_SECRET = os.getenv('JWT_SECRET', 'dev-jwt-secret-change-in-production')
    else:
        # Production: fail immediately if secrets not provided
        _secret = os.getenv('SECRET_KEY')
        _jwt_secret = os.getenv('JWT_SECRET')
        
        if not _secret or len(_secret) < 32:
            raise RuntimeError(
                "ERROR: SECRET_KEY must be set and at least 32 characters in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not _jwt_secret or len(_jwt_secret) < 32:
            raise RuntimeError(
                "ERROR: JWT_SECRET must be set and at least 32 characters in production. "
                "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        
        SECRET_KEY = _secret
        JWT_SECRET = _jwt_secret
    
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'SQLALCHEMY_DATABASE_URI',
        'sqlite:///expenses.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection pooling - only for non-SQLite databases
    # SQLite uses StaticPool and doesn't support pool_size/max_overflow
    _db_uri = SQLALCHEMY_DATABASE_URI.lower()
    if _db_uri.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS = {}
    else:
        # PostgreSQL, MySQL, etc. benefit from connection pooling
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 20,            # Number of connections to keep
            'max_overflow': 40,         # Additional connections if pool exhausted
            'pool_pre_ping': True,      # Verify connection before using
            'pool_recycle': 3600,       # Recycle connections after 1 hour
            'echo': False,              # Set to True in dev for SQL debugging
        }
    
    # Upload configuration
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads/receipts')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xlsx'}
    
    # Email configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 25))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'False') == 'True'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@expensetracker.com')
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL')
    
    # Security
    FORCE_HTTPS = os.getenv('FORCE_HTTPS', 'False') == 'True'
    
    # App URL
    APP_URL = os.getenv('APP_URL', 'http://localhost:5000')
    
    # Sentry (error tracking)
    SENTRY_DSN = os.getenv('SENTRY_DSN')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    FORCE_HTTPS = True


def get_config(env=None):
    """Get configuration by environment."""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    config_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
    }
    
    return config_map.get(env, DevelopmentConfig)
