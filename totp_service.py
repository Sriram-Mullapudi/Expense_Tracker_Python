"""2FA/TOTP integration for Flask authentication routes."""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64
from models import db, User


class TwoFactorAuthService:
    """Service for handling 2FA/TOTP authentication."""

    @staticmethod
    def enable_totp(user: User) -> Tuple[str, str]:
        """
        Enable TOTP for a user.
        
        Generates a new TOTP secret and returns both the secret
        and a QR code that can be scanned by authenticator apps.
        
        Args:
            user: User object
        
        Returns:
            Tuple of (secret_key, qr_code_data_url):
                secret_key: Base32-encoded secret for manual entry
                qr_code_data_url: Data URL of QR code image for scanning
        """
        # Generate new secret
        secret = pyotp.random_base32()
        
        # Generate provisioning URI for QR code
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name='Expense Tracker'
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color='black', back_color='white')
        
        # Convert to base64 data URL
        buffered = io.BytesIO()
        img.save(buffered, format='PNG')
        img_str = base64.b64encode(buffered.getvalue()).decode()
        qr_code_url = f"data:image/png;base64,{img_str}"
        
        return secret, qr_code_url

    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        Verify a TOTP token.
        
        Args:
            secret: User's TOTP secret key
            token: 6-digit token from authenticator app
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            # Allow for time sync issues (±30 seconds)
            return totp.verify(token, valid_window=1)
        except Exception:
            return False

    @staticmethod
    def confirm_totp_setup(user: User, secret: str, token: str) -> bool:
        """
        Confirm and save TOTP setup for a user.
        
        Verifies the token before saving to ensure the secret is correct.
        
        Args:
            user: User object
            secret: TOTP secret to save
            token: Verification token from authenticator app
        
        Returns:
            True if setup confirmed and saved, False if verification failed
        """
        if not TwoFactorAuthService.verify_totp(secret, token):
            return False
        
        # Save TOTP secret to user
        user.totp_secret = secret
        user.totp_enabled = True
        db.session.commit()
        
        return True

    @staticmethod
    def disable_totp(user: User) -> None:
        """
        Disable TOTP for a user.
        
        Args:
            user: User object
        """
        user.totp_secret = None
        user.totp_enabled = False
        db.session.commit()

    @staticmethod
    def generate_backup_codes(user: User, count: int = 10) -> list:
        """
        Generate backup codes for account recovery.
        
        Backup codes are 8-character alphanumeric codes that can be used
        if the user loses access to their authenticator app.
        
        Args:
            user: User object
            count: Number of codes to generate (default 10)
        
        Returns:
            List of backup codes
        """
        import secrets
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        
        # Store hashed codes
        from werkzeug.security import generate_password_hash
        user.backup_codes = '|'.join(
            generate_password_hash(code) for code in codes
        )
        db.session.commit()
        
        return codes

    @staticmethod
    def verify_backup_code(user: User, code: str) -> bool:
        """
        Verify and use a backup code.
        
        Removes the used backup code from the user's account.
        
        Args:
            user: User object
            code: Backup code to verify
        
        Returns:
            True if code is valid, False otherwise
        """
        from werkzeug.security import check_password_hash
        
        if not user.backup_codes:
            return False
        
        codes = user.backup_codes.split('|')
        
        for stored_code in codes:
            if check_password_hash(stored_code, code):
                # Remove used code
                codes.remove(stored_code)
                user.backup_codes = '|'.join(codes)
                db.session.commit()
                return True
        
        return False


def require_2fa(f):
    """
    Decorator to require 2FA verification for a route.
    
    Should be used after @login_required to ensure user is authenticated.
    Checks if user has 2FA enabled and if session has 2FA verification.
    """
    from functools import wraps
    from flask import redirect, url_for, session
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        
        # If user has 2FA enabled but hasn't verified in this session
        if current_user.totp_enabled and not session.get('2fa_verified'):
            return redirect(url_for('auth.verify_2fa'))
        
        return f(*args, **kwargs)
    
    return decorated_function
