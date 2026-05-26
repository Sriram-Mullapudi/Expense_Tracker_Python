"""Authentication routes (login, register, password reset).

REFACTORED TO USE SERVICE LAYER
- Routes now only handle: request parsing, error handling, response formatting
- All business logic moved to AuthService
- All validation via Pydantic schemas
- Clean separation from Flask concerns
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from pydantic import ValidationError
from datetime import datetime, timedelta, timezone

from services.auth_service import AuthService
from services.validators import (
    LoginRequest, 
    RegisterRequest, 
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from rate_limit import limiter, TIER_AUTH_STRICT, TIER_AUTH_VERIFY

auth_bp = Blueprint('auth', __name__, url_prefix='/')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(TIER_AUTH_STRICT)  # Max 5 per minute, 20 per hour
def login():
    """
    User login route.
    
    REFACTORED FLOW:
    1. Parse request
    2. Validate with Pydantic (LoginRequest)
    3. Call AuthService.login() for pure business logic
    4. Handle Flask-specific concerns (login_user, flash, redirect)
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            # Validate request data using Pydantic
            login_data = LoginRequest(
                username=request.form.get('username', '').strip(),
                password=request.form.get('password', ''),
                remember=request.form.get('remember', False) == 'on'
            )
            
            # Call service for authentication (NO Flask here)
            result = AuthService.login(login_data.username, login_data.password)
            
            if result['success']:
                # Load user from database for Flask-Login
                from models import User
                user = User.query.get(result['user']['id'])
                login_user(user, remember=login_data.remember)
                
                # Handle redirect
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('dashboard.index'))
        
        except ValidationError as ve:
            # Pydantic validation error
            errors = ve.errors()
            flash(f"Invalid input: {errors[0]['msg']}", 'danger')
        
        except ValueError as ve:
            # Service layer validation error
            flash(str(ve), 'danger')
        
        except Exception as e:
            flash(f"Login failed: {str(e)}", 'danger')
    
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit(TIER_AUTH_STRICT)  # Max 5 per minute, 20 per hour
def register():
    """
    User registration route.
    
    REFACTORED FLOW:
    1. Parse form data
    2. Validate with Pydantic (RegisterRequest) - enforces 12+ char password, special chars, etc
    3. Call AuthService.register() for pure business logic
    4. Handle Flask concerns (login_user, flash, email)
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            # Validate request data with Pydantic
            # This automatically enforces: username 3-80 chars, email format,
            # password 12+ chars with uppercase/lowercase/digit/special char
            register_data = RegisterRequest(
                username=request.form.get('username', '').strip(),
                email=request.form.get('email', '').strip(),
                password=request.form.get('password', ''),
                confirm_password=request.form.get('confirm_password', '')
            )
            
            # Call service for registration (NO Flask here)
            result = AuthService.register(
                register_data.username,
                register_data.email,
                register_data.password
            )
            
            if result['success']:
                # Load user for Flask-Login
                from models import User
                user = User.query.get(result['user']['id'])
                login_user(user)
                flash('Account created successfully! Welcome!', 'success')
                return redirect(url_for('dashboard.index'))
        
        except ValidationError as ve:
            # Pydantic validation - very clear error messages
            errors = ve.errors()
            flash(f"Invalid input: {errors[0]['msg']}", 'danger')
        
        except ValueError as ve:
            # Service layer validation
            flash(str(ve), 'danger')
        
        except Exception as e:
            flash(f"Registration failed: {str(e)}", 'danger')
    
    return render_template('register.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit(TIER_AUTH_VERIFY)  # Slower tier: 10 per minute, 50 per hour
def forgot_password():
    """
    Password reset request route.
    
    REFACTORED FLOW:
    1. Parse email
    2. Validate with Pydantic
    3. Call service to send reset email (NO Flask here)
    4. Return success message (don't reveal if email exists - security best practice)
    """
    if request.method == 'POST':
        try:
            # Validate email format
            forgot_data = ForgotPasswordRequest(
                email=request.form.get('email', '').strip()
            )
            
            # Call service (handles email sending, token generation)
            result = AuthService.request_password_reset(forgot_data.email)
            
            flash(result['message'], 'info')
            return redirect(url_for('login'))
        
        except ValidationError as ve:
            errors = ve.errors()
            flash(f"Invalid input: {errors[0]['msg']}", 'danger')
        
        except Exception as e:
            flash(f"Request failed: {str(e)}", 'danger')
    
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit(TIER_AUTH_VERIFY)
def reset_password(token: str):
    """
    Reset password with token route.
    
    REFACTORED FLOW:
    1. Parse new password
    2. Validate with Pydantic (14+ char password with special chars)
    3. Call service to reset password
    4. Handle redirect
    """
    if request.method == 'POST':
        try:
            # Validate new password
            reset_data = ResetPasswordRequest(
                token=token,
                password=request.form.get('password', '')
            )
            
            # Call service for password reset
            result = AuthService.reset_password(reset_data.token, reset_data.password)
            
            if result['success']:
                flash('Password reset successful! Please log in.', 'success')
                return redirect(url_for('login'))
        
        except ValidationError as ve:
            errors = ve.errors()
            flash(f"Invalid input: {errors[0]['msg']}", 'danger')
        
        except ValueError as ve:
            flash(str(ve), 'danger')
        
        except Exception as e:
            flash(f"Reset failed: {str(e)}", 'danger')
    
    return render_template('reset_password.html', token=token)


@auth_bp.route('/forgot-username', methods=['GET', 'POST'])
@limiter.limit(TIER_AUTH_VERIFY)
def forgot_username():
    """
    Username recovery route.
    
    REFACTORED FLOW:
    1. Parse email
    2. Call service to send username via email
    3. Return generic success message (security: don't reveal if email exists)
    """
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            
            # Call service to send username recovery
            result = AuthService.recover_username(email)
            
            flash(result['message'], 'info')
            return redirect(url_for('login'))
        
        except Exception as e:
            flash(f"Request failed: {str(e)}", 'danger')
    
    return render_template('forgot_username.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))
