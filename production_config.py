"""Production-grade configuration management using Pydantic."""

import os
from datetime import timedelta
from urllib.parse import quote_plus
from typing import Optional

class Settings:
    """Application settings loaded from environment variables."""
    
    # Environment
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
    
    # Flask & Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production-immediately")
    FLASK_ENV = ENV
    
    # Database Configuration
    DB_USER = os.getenv("DB_USER", "expense_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "expense_tracker_db")
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Generate PostgreSQL connection string based on environment."""
        if self.ENV == "development":
            # Development: simpler connection
            return f"postgresql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        else:
            # Production: with SSL and connection pooling
            return f"postgresql+psycopg2://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?connect_timeout=10&sslmode=require"
    
    # SQLAlchemy Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG
    
    # Connection pooling settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "echo": False,
        "pool_size": 10,
        "pool_recycle": 3600,  # Recycle connections every hour
        "pool_pre_ping": True,  # Test connections before using
        "max_overflow": 20,
        "pool_timeout": 30,
        "connect_args": {
            "connect_timeout": 10,
        }
    }
    
    # Session & Cookie Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection
    
    # Email Configuration
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@expensetracker.com")
    MAIL_MAX_EMAILS = 100  # Rate limit emails
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    UPLOAD_FOLDER = "uploads"
    UPLOAD_MAX_SIZE = 5 * 1024 * 1024  # 5MB per file
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp"}
    
    # Security Configuration
    ENABLE_2FA = True
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL = True
    PASSWORD_EXPIRY_DAYS = 90 if not DEBUG else 0  # No expiry in dev
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_DEFAULT = "200 per day, 50 per hour"
    
    # Redis Configuration (for caching & sessions)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Monitoring & Observability
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    SENTRY_TRACES_SAMPLE_RATE = 0.1 if not DEBUG else 1.0
    
    # Logging
    LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
    LOG_FILE = "logs/app.log"
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # API Configuration
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = DEBUG
    
    # Feature Flags
    ENABLE_ANALYTICS = True
    ENABLE_BUDGET_ALERTS = True
    ENABLE_FILE_UPLOAD = True
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings instance from environment."""
        return cls()


# Create default settings instance
settings = Settings.from_env()
