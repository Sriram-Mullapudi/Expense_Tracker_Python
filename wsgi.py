"""WSGI Entry Point for Production Deployment

This module initializes the Flask application for production deployment
using gunicorn or other WSGI servers.

Usage:
    gunicorn wsgi:app
    gunicorn wsgi:app --workers 4 --timeout 120 --bind 0.0.0.0:5000
"""

import os
import logging
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import and create the Flask application using the factory pattern
from factory import create_app

# Create Flask app instance
app = create_app()

# Log startup information
if __name__ != "__main__":
    app.logger.info("=" * 80)
    app.logger.info("WSGI Application Initialized")
    app.logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    app.logger.info(f"Debug Mode: {app.debug}")
    app.logger.info("=" * 80)
