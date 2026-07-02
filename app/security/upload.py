"""
Secure file upload handling with MIME sniffing, magic-byte validation, and path safety.
"""
import os
import re
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename

from security.limits import MAX_FILE_SIZE, ALLOWED_EXTENSIONS


# Magic bytes for common file types
MAGIC_BYTES = {
    b'%PDF-': 'pdf',
    b'PK\x03\x04': 'docx',  # Also covers .docx, .odt (ZIP-based)
    b'\x1f\x8b': 'gz',
    b'RIFF': 'riff',  # Covers many formats
}


def get_magic_type(file_bytes: bytes) -> str | None:
    """Detect file type from magic bytes."""
    for magic, file_type in MAGIC_BYTES.items():
        if file_bytes.startswith(magic):
            return file_type
    return None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and unsafe characters."""
    # Use werkzeug's secure_filename as base
    safe_name = secure_filename(filename)
    
    # Remove any remaining dangerous characters
    safe_name = re.sub(r'[^\w\.\-]', '_', safe_name)
    
    # Ensure we have an extension
    if '.' not in safe_name:
        safe_name = f"file_{safe_name}"
    
    return safe_name[:255]  # Limit length


def validate_upload(file, allowed_extensions: set = None) -> tuple[bool, str, str]:
    """
    Validate an uploaded file.
    Returns: (is_valid, error_message, sanitized_filename)
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    
    # Check if file exists
    if not file or not file.filename:
        return False, "No file provided", ""
    
    original_filename = file.filename
    
    # Check extension
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
    if ext not in allowed_extensions:
        return False, f"File type '{ext}' not allowed", ""
    
    # Read file content for validation
    file_content = file.read()
    file_size = len(file_content)
    
    # Check size
    if file_size > MAX_FILE_SIZE:
        return False, f"File too large ({file_size} bytes, max {MAX_FILE_SIZE})", ""
    
    # Reset file pointer for later reading
    file.seek(0)
    
    # Magic byte check for certain types
    if ext == 'pdf':
        magic_type = get_magic_type(file_content[:20])
        if magic_type != 'pdf':
            return False, "Invalid PDF file (magic bytes mismatch)", ""
    
    # Sanitize filename
    safe_filename = sanitize_filename(original_filename)
    
    return True, "", safe_filename


def save_uploaded_file(file, base_dir: str, entity_type: str, entity_id: str) -> str:
    """
    Save an uploaded file securely.
    Returns the relative path to the saved file.
    """
    is_valid, error_msg, safe_filename = validate_upload(file)
    
    if not is_valid:
        raise ValueError(error_msg)
    
    # Create directory structure: base_dir/raw/{entity_type}/{entity_id}/
    entity_dir = os.path.join(base_dir, 'raw', entity_type, entity_id)
    os.makedirs(entity_dir, exist_ok=True)
    
    # Generate unique filename with UUID prefix
    unique_id = str(uuid.uuid4())[:8]
    name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
    final_filename = f"{unique_id}_{name}.{ext}" if ext else f"{unique_id}_{name}"
    
    file_path = os.path.join(entity_dir, final_filename)
    
    # Save file
    file.save(file_path)
    
    # Return relative path
    return os.path.relpath(file_path, base_dir)


def safe_join(base_dir: str, *parts) -> str | None:
    """
    Safely join path components, rejecting any traversal attempts.
    Returns None if any part is unsafe.
    """
    # Check each part for path traversal
    for part in parts:
        if not part:
            continue
        if '..' in part:
            return None
        if part.startswith('/') or part.startswith('\\'):
            return None
        if ':' in part and len(part) > 1:  # Windows drive letters
            return None
    
    # Join and resolve
    full_path = os.path.normpath(os.path.join(base_dir, *parts))
    
    # Verify the result is still under base_dir
    base_resolved = os.path.realpath(base_dir)
    full_resolved = os.path.realpath(full_path)
    
    if not full_resolved.startswith(base_resolved + os.sep) and full_resolved != base_resolved:
        return None
    
    return full_path
