# file_upload_utils.py
# File Upload Utilities for FCCPC Portal
# Phase 3: File Attachments System

import os
import uuid
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename

# Upload Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
MAX_FILES_PER_REPORT = 5

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    # Documents
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    
    # Spreadsheets
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    
    # Images
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif'
}

# File type icons for display
FILE_ICONS = {
    'pdf': 'bi-file-earmark-pdf-fill text-danger',
    'doc': 'bi-file-earmark-word-fill text-primary',
    'docx': 'bi-file-earmark-word-fill text-primary',
    'xls': 'bi-file-earmark-excel-fill text-success',
    'xlsx': 'bi-file-earmark-excel-fill text-success',
    'jpg': 'bi-file-earmark-image-fill text-info',
    'jpeg': 'bi-file-earmark-image-fill text-info',
    'png': 'bi-file-earmark-image-fill text-info',
    'gif': 'bi-file-earmark-image-fill text-info',
    'default': 'bi-file-earmark-fill text-secondary'
}


def allowed_file(filename):
    """
    Check if file extension is allowed
    
    Args:
        filename (str): Original filename
        
    Returns:
        bool: True if allowed, False otherwise
    """
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def get_file_extension(filename):
    """
    Get file extension from filename
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: File extension (lowercase)
    """
    if '.' not in filename:
        return ''
    
    return filename.rsplit('.', 1)[1].lower()


def get_file_icon(filename):
    """
    Get Bootstrap icon class for file type
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Bootstrap icon class
    """
    extension = get_file_extension(filename)
    return FILE_ICONS.get(extension, FILE_ICONS['default'])


def generate_unique_filename(original_filename):
    """
    Generate unique filename to prevent overwrites
    
    Args:
        original_filename (str): Original filename from user
        
    Returns:
        str: Unique filename
    """
    # Secure the filename first
    safe_filename = secure_filename(original_filename)
    
    # Get extension
    extension = get_file_extension(safe_filename)
    
    # Generate unique ID
    unique_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create unique filename: timestamp_uuid.extension
    if extension:
        unique_filename = f"{timestamp}_{unique_id}.{extension}"
    else:
        unique_filename = f"{timestamp}_{unique_id}"
    
    return unique_filename


def validate_file_size(file):
    """
    Check if file size is within limits
    
    Args:
        file: FileStorage object
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Get file size by seeking to end
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if size > MAX_FILE_SIZE:
        size_mb = size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return False, f"File too large ({size_mb:.1f}MB). Maximum size is {max_mb}MB."
    
    return True, None


def validate_file(file):
    """
    Validate uploaded file
    
    Args:
        file: FileStorage object
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check if file exists
    if not file or file.filename == '':
        return False, "No file provided"
    
    # Check file extension
    if not allowed_file(file.filename):
        allowed_list = ', '.join(ALLOWED_EXTENSIONS.keys())
        return False, f"File type not allowed. Allowed types: {allowed_list}"
    
    # Check file size
    is_valid_size, size_error = validate_file_size(file)
    if not is_valid_size:
        return False, size_error
    
    return True, None


def save_file(file, folder_key):
    """
    Save uploaded file to disk.
    folder_key can be an int (legacy) or a string like 'report_5' or 'complaint_12'.
    """
    try:
        is_valid, error = validate_file(file)
        if not is_valid:
            return False, None, error

        report_folder = os.path.join(UPLOAD_FOLDER, str(folder_key))
        os.makedirs(report_folder, exist_ok=True)

        unique_filename = generate_unique_filename(file.filename)
        file_path = os.path.join(report_folder, unique_filename)

        file.save(file_path)
        os.chmod(file_path, 0o644)

        return True, unique_filename, None

    except Exception as e:
        return False, None, f"Error saving file: {str(e)}"


def delete_file(folder_key, filename):
    """Delete file from disk."""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, str(folder_key), filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True, None
        return False, "File not found"
    except Exception as e:
        return False, f"Error deleting file: {str(e)}"


def get_file_path(folder_key, filename):
    """Get full path to file."""
    return os.path.join(UPLOAD_FOLDER, str(folder_key), filename)


def format_file_size(size_bytes):
    """
    Format file size in human-readable format
    
    Args:
        size_bytes (int): File size in bytes
        
    Returns:
        str: Formatted size (e.g., "2.5 MB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def calculate_file_hash(file_path):
    """
    Calculate SHA-256 hash of file for integrity verification
    
    Args:
        file_path (str): Path to file
        
    Returns:
        str: SHA-256 hash
    """
    sha256_hash = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        # Read file in chunks for memory efficiency
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def cleanup_orphaned_files():
    """
    Clean up files that don't have database records
    This should be run periodically as maintenance
    
    Returns:
        tuple: (files_deleted, errors)
    """
    # This is a placeholder for a maintenance script
    # Implementation would query database and compare with filesystem
    pass


# Initialize upload folder
def init_upload_folder():
    """
    Initialize upload folder with proper permissions
    
    Returns:
        tuple: (success, error_message)
    """
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        os.chmod(UPLOAD_FOLDER, 0o755)
        return True, None
    except Exception as e:
        return False, f"Error creating upload folder: {str(e)}"


if __name__ == "__main__":
    # Test initialization
    success, error = init_upload_folder()
    if success:
        print(f"✅ Upload folder initialized: {UPLOAD_FOLDER}")
    else:
        print(f"❌ Error: {error}")
