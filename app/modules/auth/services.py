"""
Authentication business logic services.

This module provides authentication services by wrapping the core database functions.
"""

import logging
from typing import Optional, Dict, Any

from app.core.database.models import (
    get_user_by_credentials as db_get_user_by_credentials,
    get_user_by_id as db_get_user_by_id,
    update_last_login as db_update_last_login,
)

logger = logging.getLogger("skillhub.auth")


def authenticate_user(employee_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user and update last login timestamp.

    Args:
        employee_id: The employee's ID
        api_key: The API key for authentication

    Returns:
        User dictionary if authentication successful, None otherwise
    """
    user = db_get_user_by_credentials(employee_id, api_key)
    if user:
        db_update_last_login(user["id"])
        logger.info(f"User authenticated: employee_id={employee_id}")
    else:
        logger.warning(f"Failed authentication attempt: employee_id={employee_id}")
    return user
