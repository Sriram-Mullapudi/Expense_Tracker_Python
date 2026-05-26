"""File upload service for handling receipts and documents - PRODUCTION GRADE.

Security features:
- Path traversal prevention (resolve real paths)
- Disk space validation
- Content-type verification (magic bytes)
- Atomic file operations  
- Detailed logging of upload events
- Safe error messages (no internal paths leaked)
- Permission enforcement (files not readable by others)
"""
from typing import Tuple, List, Optional, BinaryIO
import os
import secrets
import logging
import shutil
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
import mimetypes
from PIL import Image
import io

# Configuration
UPLOAD_FOLDER = 'uploads/receipts'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
ALLOWED_MIMETYPES = {
    'image/jpeg': ['jpg', 'jpeg'],
    'image/png': ['png'],
    'image/gif': ['gif'],
    'application/pdf': ['pdf'],
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_SIZE = (2000, 2000)  # Max dimensions for images
THUMBNAIL_SIZE = (200, 200)
MIN_DISK_SPACE = 100 * 1024 * 1024  # Require 100MB free space

logger = logging.getLogger(__name__)


class FileUploadError(Exception):
    """Custom exception for file upload errors."""
    pass


def init_upload_folder() -> None:
    """Initialize upload folder if it doesn't exist.
    
    Sets up secure directory structure with restricted permissions.
    """
    try:
        Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True, mode=0o700)
        logger.info(f"Upload folder initialized: {UPLOAD_FOLDER}")
    except Exception as e:
        logger.error(f"Failed to initialize upload folder: {e}")
        raise FileUploadError("Upload storage initialization failed")


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(file: BinaryIO) -> int:
    """Get file size in bytes."""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def validate_file(file: Optional[BinaryIO]) -> List[str]:
    """Validate uploaded file with comprehensive checks.
    
    Args:
        file: File object to validate
    
    Returns:
        List of error messages (empty list if valid)
    """
    errors = []
    
    if not file:
        errors.append('No file provided')
        return errors
    
    if file.filename == '':
        errors.append('No file selected')
        return errors
    
    # Check extension
    if not allowed_file(file.filename):
        errors.append(f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
        return errors
    
    # Check file size
    file_size = get_file_size(file)
    if file_size == 0:
        errors.append('File is empty')
        return errors
    
    if file_size > MAX_FILE_SIZE:
        errors.append(f'File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024):.1f}MB')
        return errors
    
    return errors


def get_file_mimetype(file: BinaryIO) -> str:
    """Get MIME type by checking file magic bytes (more secure than extension).
    
    Args:
        file: File object to check
    
    Returns:
        MIME type string
    """
    # Read magic bytes
    file.seek(0)
    header = file.read(32)
    file.seek(0)
    
    # Check file signatures (magic bytes)
    if header[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    elif header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    elif header[:6] in [b'GIF87a', b'GIF89a']:
        return 'image/gif'
    elif header[:4] == b'%PDF':
        return 'application/pdf'
    else:
        return 'application/octet-stream'


def optimize_image(file: BinaryIO) -> BinaryIO:
    """Optimize image: resize, compress, and save.
    
    Args:
        file: Image file object
    
    Returns:
        Optimized image as BytesIO object
    
    Raises:
        FileUploadError: If image processing fails
    """
    try:
        file.seek(0)
        img = Image.open(file)
        
        # Validate image dimensions (prevent DOS attacks)
        if img.size[0] > 10000 or img.size[1] > 10000:
            raise FileUploadError("Image dimensions too large")
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        
        # Resize if too large
        if img.size[0] > MAX_IMAGE_SIZE[0] or img.size[1] > MAX_IMAGE_SIZE[1]:
            img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        
        # Optimize
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        return output
    except Exception as e:
        logger.error(f"Image optimization failed: {e}")
        raise FileUploadError("Image processing failed")


def check_disk_space() -> bool:
    """Check if sufficient disk space is available.
    
    Returns:
        True if space available, False otherwise
    """
    try:
        stat = shutil.disk_usage(UPLOAD_FOLDER if os.path.exists(UPLOAD_FOLDER) else '.')
        return stat.free > MIN_DISK_SPACE
    except Exception as e:
        logger.error(f"Failed to check disk space: {e}")
        return False


def save_upload_file(file: BinaryIO, user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Save uploaded file securely with comprehensive validation.
    
    Args:
        file: File object to save
        user_id: User ID for folder organization
    
    Returns:
        Tuple of (filename, error_message):
            On success: (filename, None)
            On failure: (None, user-safe error message)
    
    Security features:
        - Path traversal prevention
        - Disk space validation
        - Content-type verification
        - Atomic file operations
        - Detailed logging
    """
    if not file or not user_id:
        logger.warning(f"Invalid upload attempt: file={bool(file)}, user_id={user_id}")
        return None, "Invalid file or user"
    
    try:
        # Validate file  
        errors = validate_file(file)
        if errors:
            logger.info(f"File validation failed for user {user_id}: {errors[0]}")
            # Return generic error to user (don't expose validation details)
            return None, "Invalid file"
        
        # Check disk space BEFORE creating directory
        if not check_disk_space():
            logger.warning(f"Low disk space for uploads")
            return None, "Storage quota exceeded"
        
        # Create user-specific directory (secure)
        user_upload_dir = Path(UPLOAD_FOLDER) / str(user_id)
        try:
            user_upload_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        except PermissionError:
            logger.error(f"No write permission to {user_upload_dir}")
            return None, "Storage unavailable"
        
        # Verify path is within UPLOAD_FOLDER (PATH TRAVERSAL PREVENTION)
        try:
            real_user_dir = user_upload_dir.resolve()
            real_upload_base = Path(UPLOAD_FOLDER).resolve()
            if not str(real_user_dir).startswith(str(real_upload_base)):
                logger.error(f"Path traversal attempt detected: {real_user_dir}")
                return None, "Invalid file path"
        except Exception as e:
            logger.error(f"Path validation failed: {e}")
            return None, "Invalid file path"
        
        # Get and validate extension
        if '.' not in file.filename:
            logger.warning(f"No extension in filename for user {user_id}: {file.filename}")
            return None, "Invalid file type"
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"Invalid extension for user {user_id}: {ext}")
            return None, "Invalid file type"
        
        # Validate MIME type (check magic bytes, not extension)
        mimetype = get_file_mimetype(file)
        expected_mimetypes = [mt for mt, exts in ALLOWED_MIMETYPES.items() if ext in exts]
        
        if expected_mimetypes and mimetype not in expected_mimetypes:
            logger.warning(
                f"MIME type mismatch for user {user_id}: "
                f"expected {expected_mimetypes}, got {mimetype}"
            )
            return None, "File content doesn't match type"
        
        # Generate cryptographically secure random filename
        file_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16]
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{file_hash}_{timestamp}.{ext}"
        filepath = user_upload_dir / filename
        temp_filepath = user_upload_dir / f"{filename}.tmp"
        
        # Double-check path is still safe (race condition check)
        try:
            real_filepath = filepath.resolve()
            if not str(real_filepath).startswith(str(real_user_dir)):
                logger.error(f"Race condition in path validation: {real_filepath}")
                return None, "Invalid file path"
        except Exception as e:
            logger.error(f"Path validation failed (race check): {e}")
            return None, "Invalid file path"
        
        # Process and save file (use temporary file for atomicity)
        try:
            file.seek(0)
            
            if ext in {'jpg', 'jpeg', 'png', 'gif'}:
                # Optimize image
                optimized = optimize_image(file)
                with open(temp_filepath, 'wb') as f:
                    f.write(optimized.getvalue())
            else:
                # Save file in chunks with size limit check
                bytes_written = 0
                chunk_size = 8192
                
                with open(temp_filepath, 'wb') as f:
                    file.seek(0)
                    while True:
                        chunk = file.read(chunk_size)
                        if not chunk:
                            break
                        bytes_written += len(chunk)
                        
                        # Ensure we don't exceed max size during write
                        if bytes_written > MAX_FILE_SIZE:
                            temp_filepath.unlink(missing_ok=True)
                            logger.warning(f"File exceeded max size during write for user {user_id}")
                            return None, "File too large"
                        
                        f.write(chunk)
            
            # Atomic rename (atomic on most filesystems)
            temp_filepath.replace(filepath)
            
            # Set restrictive permissions (owner read/write only)
            os.chmod(filepath, 0o600)
            
            # Log successful upload
            file_size = filepath.stat().st_size
            logger.info(
                f"File uploaded successfully",
                extra={
                    'user_id': user_id,
                    'filename': filename,
                    'size': file_size,
                    'original_filename': file.filename,
                }
            )
            
            return filename, None
            
        except FileUploadError as e:
            temp_filepath.unlink(missing_ok=True)
            return None, str(e)
        except Exception as e:
            temp_filepath.unlink(missing_ok=True)
            logger.error(f"File processing error for user {user_id}: {e}")
            return None, "File processing failed"
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in save_upload_file for user {user_id}")
        return None, "Upload failed - please try again"


def delete_upload_file(filename: str, user_id: int) -> bool:
    """Delete uploaded file with authorization check.
    
    Args:
        filename: Name of file to delete
        user_id: User ID (must own the file)
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        filepath = Path(UPLOAD_FOLDER) / str(user_id) / filename
        
        # Verify path is within user's folder (prevent deletion of other user's files)
        real_filepath = filepath.resolve()
        user_dir = (Path(UPLOAD_FOLDER) / str(user_id)).resolve()
        
        if not str(real_filepath).startswith(str(user_dir)):
            logger.warning(f"Unauthorized file delete attempt: {filepath}")
            return False
        
        if filepath.exists():
            filepath.unlink()
            logger.info(f"File deleted: user_id={user_id}, filename={filename}")
            return True
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
    return False


def get_file_url(filename: str, user_id: int) -> str:
    """Get URL for uploaded file with user ID in path.
    
    Args:
        filename: Name of file
        user_id: User ID
    
    Returns:
        Relative URL path for the file
    """
    return f'/uploads/receipts/{user_id}/{filename}'


def get_file_path(filename: str, user_id: int) -> Optional[str]:
    """Get full file path with authorization check.
    
    Args:
        filename: Name of file
        user_id: User ID (must own the file)
    
    Returns:
        Full file system path if authorized, None otherwise
    """
    try:
        filepath = Path(UPLOAD_FOLDER) / str(user_id) / filename
        
        # Verify authorization
        real_filepath = filepath.resolve()
        user_dir = (Path(UPLOAD_FOLDER) / str(user_id)).resolve()
        
        if not str(real_filepath).startswith(str(user_dir)):
            logger.warning(f"Unauthorized file access attempt: {filepath}")
            return None
        
        if filepath.exists():
            return str(filepath)
    except Exception as e:
        logger.error(f"File path resolution error: {e}")
    
    return None


def file_exists(filename: str, user_id: int) -> bool:
    """Check if file exists for user.
    
    Args:
        filename: Name of file to check
        user_id: User ID (must own the file)
    
    Returns:
        True if file exists and user is authorized, False otherwise
    """
    path = get_file_path(filename, user_id)
    return path is not None and Path(path).exists()
