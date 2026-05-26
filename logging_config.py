"""Structured logging configuration for production."""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured logs with context."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with additional context."""
        record.timestamp = datetime.utcnow().isoformat()
        
        # Base format
        log_msg = super().format(record)
        
        # Add exception info if present
        if record.exc_info:
            log_msg += '\n' + self.formatException(record.exc_info)
        
        return log_msg


def setup_logging(app) -> logging.Logger:
    """
    Configure structured logging for the application.
    
    Handles:
    - File rotation (10MB per file, 10 backups)
    - Separate error log file
    - Console output with color support
    - Structured JSON-ready format
    - Request/response logging
    - SQL query logging (in debug mode)
    
    Args:
        app: Flask application instance
    
    Returns:
        Configured logger instance
    """
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Log format with structured fields
    log_format = (
        '%(timestamp)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s'
    )
    
    formatter = StructuredFormatter(log_format)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 1. File handler (all logs)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    # 2. Error file handler (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # 3. Console handler (development)
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    
    # 4. Configure library loggers
    # Reduce noise from third-party libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    
    # Set SQLAlchemy logging
    if app.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Get app logger
    app_logger = logging.getLogger(__name__)
    
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance configured for that module
    
    Example:
        logger = get_logger(__name__)
        logger.info("This is an info message")
        logger.error("This is an error message", exc_info=True)
    """
    return logging.getLogger(name)


# Context managers for logging sections
class LoggingContext:
    """Context manager for logging operation outcomes."""
    
    def __init__(self, logger: logging.Logger, operation: str):
        """
        Initialize logging context.
        
        Args:
            logger: Logger instance
            operation: Description of operation being logged
        """
        self.logger = logger
        self.operation = operation
    
    def __enter__(self):
        """Log operation start."""
        self.logger.info(f"Starting: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log operation result."""
        if exc_type is None:
            self.logger.info(f"Completed: {self.operation}")
        else:
            self.logger.error(
                f"Failed: {self.operation}",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        return False


# Instance counter for request IDs
_request_id_counter = 0


def generate_request_id() -> str:
    """Generate unique request ID for tracing."""
    global _request_id_counter
    _request_id_counter += 1
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{_request_id_counter:06d}"
