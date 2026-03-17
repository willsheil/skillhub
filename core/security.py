"""
Security utilities for SkillHub application.

Provides functions for:
- API key hashing and verification
- Token generation
- Sensitive data masking
"""

import hashlib
import secrets
import re
from typing import Any, Dict, Optional
from functools import wraps

from .constants import API_KEY_LENGTH


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256.

    Args:
        api_key: Plain text API key

    Returns:
        Hashed API key string

    Example:
        >>> hashed = hash_api_key("my-secret-key-12345")
        >>> print(hashed)
        5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash.

    Args:
        plain_key: Plain text API key to verify
        hashed_key: Expected hashed API key

    Returns:
        True if the key matches, False otherwise
    """
    return hash_api_key(plain_key) == hashed_key


def generate_token(length: int = 32) -> str:
    """Generate a random token.

    Args:
        length: Length of the token (default 32)

    Returns:
        Random token string

    Example:
        >>> token = generate_token()
        >>> len(token)
        32
    """
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """Generate a new API key.

    Returns:
        New API key string
    """
    return f"sk_{secrets.token_urlsafe(API_KEY_LENGTH)}"


def mask_sensitive_data(data: Dict[str, Any], fields: Optional[list] = None) -> Dict[str, Any]:
    """Mask sensitive fields in a dictionary.

    Args:
        data: Dictionary containing data to mask
        fields: List of field names to mask. If None, uses default fields.

    Returns:
        Dictionary with sensitive fields masked

    Example:
        >>> data = {"password": "secret123", "api_key": "sk_abc123"}
        >>> masked = mask_sensitive_data(data)
        >>> print(masked)
        {'password': '***', 'api_key': '***'}
    """
    default_fields = ["password", "api_key", "token", "secret", "authorization"]
    mask_fields = fields or default_fields

    masked = data.copy()
    for field in mask_fields:
        if field in masked:
            masked[field] = "***"

    return masked


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename

    Example:
        >>> sanitize_filename("../../../etc/passwd")
        ''
        >>> sanitize_filename("my file.zip")
        'my_file.zip'
    """
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]

    # Replace invalid characters
    filename = re.sub(r'[^\w\-.]', '_', filename)

    # Prevent empty filename
    if not filename or filename == "_":
        return ""

    return filename


def validate_skill_name(name: str) -> bool:
    """Validate skill name format.

    Args:
        name: Skill name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False

    # Allow lowercase letters, numbers, and hyphens
    # Must start and end with alphanumeric
    pattern = r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$'
    return bool(re.match(pattern, name)) and len(name) <= 64


def validate_version(version: str) -> bool:
    """Validate semantic version format.

    Args:
        version: Version string to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> validate_version("1.0.0")
        True
        >>> validate_version("1.0")
        False
        >>> validate_version("v1.0.0")
        False
    """
    pattern = r'^\d+\.\d+\.\d+$'
    return bool(re.match(pattern, version))
