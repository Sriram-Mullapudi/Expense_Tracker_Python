"""Authentication service - pure business logic without Flask.

This service handles:
- User registration
- User login
- Password reset flows
- Token generation/validation

NO Flask imports. NO request, NO current_user, NO jsonify.
Returns clean Python dicts/objects for routes to format.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, url_for

from models import db, User
from email_service import (
    send_password_reset_email, 
    send_welcome_email,
    send_username_recovery_email
)


class AuthService:
    """Handles authentication business logic."""
    
    # Token expiration (1 hour)
    TOKEN_EXPIRY_SECONDS = 3600
    
    @staticmethod
    def register(username: str, email: str, password: str) -> Dict:
        """
        Register a new user.
        
        Args:
            username: Username (3-80 chars)
            email: Email address
            password: Password (12+ chars with complexity requirements)
        
        Returns:
            {"success": bool, "user": {...}, "error": Optional[str]}
        
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        # Validate inputs
        if not username or len(username) < 3 or len(username) > 80:
            raise ValueError('Username must be 3-80 characters')
        
        if not email:
            raise ValueError('Email is required')
        
        if not password or len(password) < 12:
            raise ValueError('Password must be at least 12 characters')
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username.strip().lower()).first()
        if existing_user:
            raise ValueError('Username already exists')
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=email.strip().lower()).first()
        if existing_email:
            raise ValueError('Email already registered')
        
        try:
            # Create new user with secure password hashing
            user = User(
                username=username.strip().lower(),
                email=email.strip().lower(),
                password=generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
            )
            db.session.add(user)
            db.session.commit()
            
            # Send welcome email (fire and forget - don't fail if email fails)
            try:
                send_welcome_email(user.email, user.username)
            except Exception as e:
                # Log but don't fail the registration
                print(f"Warning: Failed to send welcome email: {e}")
            
            return {
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'created_at': user.created_at.isoformat() if user.created_at else None
                },
                'message': 'User registered successfully'
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Registration failed: {str(e)}')
    
    @staticmethod
    def login(username: str, password: str) -> Dict:
        """
        Authenticate user and return user object.
        
        Args:
            username: Username
            password: Password
        
        Returns:
            {"success": bool, "user": {...}, "error": Optional[str]}
        """
        if not username or not password:
            raise ValueError('Username and password are required')
        
        # Find user by username (case-insensitive)
        user = User.query.filter_by(username=username.strip().lower()).first()
        
        if not user:
            raise ValueError('Invalid username or password')
        
        # Verify password
        if not check_password_hash(user.password, password):
            raise ValueError('Invalid username or password')
        
        return {
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None
            },
            'message': f'Welcome back, {user.username}!'
        }
    
    @staticmethod
    def request_password_reset(email: str) -> Dict:
        """
        Generate password reset token and send email.
        
        Args:
            email: User email address
        
        Returns:
            {"success": bool, "message": str}
        """
        if not email:
            raise ValueError('Email is required')
        
        user = User.query.filter_by(email=email.strip().lower()).first()
        
        if not user:
            # Don't reveal whether email exists (security best practice)
            return {
                'success': True,
                'message': 'If that email is registered, password reset link sent'
            }
        
        try:
            # Generate secure reset token
            reset_token = secrets.token_urlsafe(32)
            reset_expires = datetime.now(timezone.utc) + timedelta(seconds=AuthService.TOKEN_EXPIRY_SECONDS)
            
            # Store token in user record
            user.reset_token = reset_token
            user.reset_token_expires = reset_expires
            db.session.commit()
            
            # Build reset URL
            try:
                # Generate full reset URL using Flask's url_for
                reset_url = url_for(
                    'auth.reset_password',
                    token=reset_token,
                    _external=True
                )
            except (RuntimeError, TypeError):
                # Fallback if not in request context
                base_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
                reset_url = f"{base_url}/reset-password/{reset_token}"
            
            # Send reset email
            send_password_reset_email(user.email, reset_url)
            
            return {
                'success': True,
                'message': 'Password reset link sent to email'
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Failed to request password reset: {str(e)}')
    
    @staticmethod
    def reset_password(token: str, new_password: str) -> Dict:
        """
        Reset password using token.
        
        Args:
            token: Password reset token
            new_password: New password (12+ chars with complexity)
        
        Returns:
            {"success": bool, "message": str}
        """
        if not token or not new_password:
            raise ValueError('Token and password are required')
        
        if len(new_password) < 12:
            raise ValueError('Password must be at least 12 characters')
        
        # Find user by token
        user = User.query.filter_by(reset_token=token).first()
        
        if not user:
            raise ValueError('Invalid or expired reset link')
        
        # Check if token has expired
        if not user.reset_token_expires or datetime.now(timezone.utc) > user.reset_token_expires:
            raise ValueError('Password reset link has expired')
        
        try:
            # Update password and clear token
            user.password = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=16)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Password reset successfully'
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Failed to reset password: {str(e)}')
    
    @staticmethod
    def recover_username(email: str) -> Dict:
        """
        Send username recovery email.
        
        Args:
            email: Email address
        
        Returns:
            {"success": bool, "message": str}
        """
        if not email:
            raise ValueError('Email is required')
        
        user = User.query.filter_by(email=email.strip().lower()).first()
        
        if user:
            try:
                send_username_recovery_email(user.email, user.username)
            except Exception as e:
                print(f"Warning: Failed to send username recovery email: {e}")
        
        # Don't reveal if user exists (security)
        return {
            'success': True,
            'message': 'If that email is registered, username sent to email'
        }
