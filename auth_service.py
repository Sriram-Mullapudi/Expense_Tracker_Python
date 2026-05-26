"""Two-Factor Authentication (2FA) service using TOTP."""

import pyotp
import qrcode
from io import BytesIO
from base64 import b64encode
from typing import Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TwoFactorAuthService:
    """
    Service for managing Two-Factor Authentication (2FA).
    
    Uses Time-based One-Time Password (TOTP) algorithm for time-based authentication.
    Compatible with Google Authenticator, Authy, Microsoft Authenticator, etc.
    """
    
    # TOTP configuration
    ISSUER_NAME = "ExpenseTracker"
    WINDOW_SIZE = 1  # Allow tokens from previous/next time window
    
    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new 2FA secret for a user.
        
        Returns:
            Base32-encoded secret string (32 characters)
        
        Example:
            secret = TwoFactorAuthService.generate_secret()
            # Returns: 'JBSWY3DPEBLW64TMMQ======'
        """
        secret = pyotp.random_base32()
        logger.debug("Generated new 2FA secret")
        return secret
    
    @staticmethod
    def get_totp(secret: str) -> pyotp.TOTP:
        """
        Get TOTP object from a secret string.
        
        Args:
            secret: Base32-encoded secret
        
        Returns:
            TOTP object for token generation/verification
        
        Raises:
            ValueError: If secret is invalid
        """
        try:
            return pyotp.TOTP(secret)
        except Exception as e:
            logger.error(f"Invalid 2FA secret: {str(e)}")
            raise ValueError("Invalid 2FA secret format")
    
    @staticmethod
    def generate_token(secret: str) -> str:
        """
        Generate current TOTP token.
        
        Args:
            secret: User's 2FA secret
        
        Returns:
            6-digit token valid for current time window (~30 seconds)
        
        Example:
            token = TwoFactorAuthService.generate_token(user.two_fa_secret)
            # Returns: '123456'
        """
        try:
            totp = TwoFactorAuthService.get_totp(secret)
            token = totp.now()
            return token
        except Exception as e:
            logger.error(f"Error generating token: {str(e)}")
            raise
    
    @staticmethod
    def verify_token(secret: str, token: str) -> bool:
        """
        Verify a TOTP token against the secret.
        
        Args:
            secret: User's 2FA secret
            token: User-provided 6-digit token
        
        Returns:
            True if token is valid, False otherwise
        
        Notes:
            - Tokens are time-based (valid for ~30 seconds)
            - WINDOW_SIZE=1 allows tokens from previous/next time window
            - This prevents user errors with time differences
        
        Example:
            is_valid = TwoFactorAuthService.verify_token(
                secret="JBSWY3DPEBLW64TMMQ======",
                token="123456"
            )
        """
        try:
            # Remove any whitespace
            token = str(token).strip()
            
            # Check token length
            if len(token) != 6:
                logger.warning(f"Invalid token length: {len(token)}")
                return False
            
            # Verify token
            totp = TwoFactorAuthService.get_totp(secret)
            is_valid = totp.verify(token, valid_window=TwoFactorAuthService.WINDOW_SIZE)
            
            if not is_valid:
                logger.warning("Token verification failed")
            
            return is_valid
        
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return False
    
    @staticmethod
    def get_backup_codes(secret: str, count: int = 10) -> list[str]:
        """
        Generate backup codes for account recovery.
        
        These codes are one-time use recovery codes in case user loses their authenticator.
        
        Args:
            secret: User's 2FA secret
            count: Number of backup codes to generate
        
        Returns:
            List of backup codes (8-character alphanumeric)
        
        Note:
            - User should write these down and store securely
            - Each code can only be used once
            - Should be hashed before storage in database
        
        Example:
            codes = TwoFactorAuthService.get_backup_codes(secret)
            # Returns: ['ABC12345', 'XYZ98765', ...]
        """
        codes = []
        for _ in range(count):
            code = pyotp.random_base32()[:8]
            codes.append(code)
        
        logger.debug(f"Generated {count} backup codes")
        return codes
    
    @staticmethod
    def generate_qr_code(
        secret: str,
        user_email: str,
        issuer: str = "ExpenseTracker"
    ) -> str:
        """
        Generate QR code for 2FA setup.
        
        User scans this with authenticator app (Google Authenticator, Authy, etc).
        
        Args:
            secret: User's 2FA secret
            user_email: User's email (for display in authenticator)
            issuer: Application name (shows in authenticator)
        
        Returns:
            Base64-encoded PNG image data (data URI ready)
        
        Example:
            qr_code = TwoFactorAuthService.generate_qr_code(
                secret="JBSWY3DPEBLW64TMMQ======",
                user_email="user@example.com"
            )
            # Can be embedded in HTML: <img src="data:image/png;base64,{qr_code}">
        """
        try:
            totp = TwoFactorAuthService.get_totp(secret)
            
            # Generate provisioning URI for QR code
            uri = totp.provisioning_uri(
                name=user_email,
                issuer_name=issuer
            )
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            
            # Convert to image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Encode to base64
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            
            qr_base64 = b64encode(buf.getvalue()).decode()
            
            logger.debug(f"Generated QR code for {user_email}")
            return qr_base64
        
        except Exception as e:
            logger.error(f"Error generating QR code: {str(e)}")
            raise
    
    @staticmethod
    def get_provisioning_uri(
        secret: str,
        user_email: str,
        issuer: str = "ExpenseTracker"
    ) -> str:
        """
        Get provisioning URI for manual entry in authenticator.
        
        For users who can't scan QR code, they can manually enter this string.
        
        Args:
            secret: User's 2FA secret
            user_email: User's email
            issuer: Application name
        
        Returns:
            otpauth:// URI string
        
        Example:
            uri = TwoFactorAuthService.get_provisioning_uri(
                secret="JBSWY3DPEBLW64TMMQ======",
                user_email="user@example.com"
            )
            # Returns: 'otpauth://totp/user%40example.com?secret=JBSWY3DPEBLW64TMMQ%3D%3D%3D%3D%3D%3D&issuer=ExpenseTracker'
        """
        try:
            totp = TwoFactorAuthService.get_totp(secret)
            uri = totp.provisioning_uri(name=user_email, issuer_name=issuer)
            return uri
        except Exception as e:
            logger.error(f"Error getting provisioning URI: {str(e)}")
            raise


class BackupCodeService:
    """Service for managing backup codes."""
    
    @staticmethod
    def hash_code(code: str) -> str:
        """
        Hash a backup code for secure storage.
        
        Args:
            code: Backup code to hash
        
        Returns:
            Hashed backup code (using bcrypt)
        """
        import bcrypt
        return bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    
    @staticmethod
    def verify_code(code: str, hashed_code: str) -> bool:
        """
        Verify a backup code against its hash.
        
        Args:
            code: User-provided backup code
            hashed_code: Stored hashed backup code
        
        Returns:
            True if code matches, False otherwise
        """
        import bcrypt
        try:
            return bcrypt.checkpw(code.encode(), hashed_code.encode())
        except Exception as e:
            logger.error(f"Error verifying backup code: {str(e)}")
            return False


class TwoFactorSetup:
    """Context manager for 2FA setup flow."""
    
    def __init__(self, user_email: str):
        """
        Initialize 2FA setup.
        
        Args:
            user_email: User's email address
        """
        self.user_email = user_email
        self.secret = TwoFactorAuthService.generate_secret()
        self.qr_code = TwoFactorAuthService.generate_qr_code(self.secret, user_email)
        self.uri = TwoFactorAuthService.get_provisioning_uri(self.secret, user_email)
        self.backup_codes = TwoFactorAuthService.get_backup_codes(self.secret)
        self.created_at = datetime.utcnow()
    
    def get_setup_data(self) -> dict:
        """
        Get all setup data for user.
        
        Returns:
            Dictionary with QR code, URI, backup codes
        
        Example:
            setup = TwoFactorSetup("user@example.com")
            data = setup.get_setup_data()
            # {
            #     "qr_code": "data:image/png;base64,...",
            #     "secret": "JBSWY3DPEBLW64TMMQ======",
            #     "uri": "otpauth://totp/...",
            #     "backup_codes": ["ABC12345", ...],
            #     "created_at": datetime
            # }
        """
        return {
            "qr_code": self.qr_code,
            "secret": self.secret,
            "uri": self.uri,
            "backup_codes": self.backup_codes,
            "created_at": self.created_at,
            "message": "Scan QR code with authenticator app. Save backup codes in safe place."
        }
    
    def verify_setup(self, token: str) -> bool:
        """
        Verify user has configured 2FA correctly.
        
        Args:
            token: Token from user's authenticator app
        
        Returns:
            True if setup verified, False otherwise
        """
        return TwoFactorAuthService.verify_token(self.secret, token)
