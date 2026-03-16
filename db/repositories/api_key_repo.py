"""
API Key repository - Database operations for API keys.

Provides methods for managing external API keys for marketplace access.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from db.connection import get_connection
from db.models import ApiKey
from core.security import hash_api_key, generate_api_key

logger = logging.getLogger(__name__)


class ApiKeyRepository:
    """Repository for API key database operations."""

    @staticmethod
    def create(
        key_name: str,
        user_id: int,
        rate_limit: int = 100,
        expires_at: Optional[datetime] = None,
    ) -> tuple[ApiKey, str]:
        """Create a new API key.

        Args:
            key_name: Human-readable name for the key
            user_id: Owner user ID
            rate_limit: Requests per minute limit
            expires_at: Optional expiration timestamp

        Returns:
            Tuple of (ApiKey object, plain text API key)
        """
        plain_key = generate_api_key()
        hashed_key = hash_api_key(plain_key)

        with get_connection() as conn:
            conn.execute(
                """INSERT INTO api_keys
                   (key_name, api_key_hash, user_id, rate_limit, expires_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (key_name, hashed_key, user_id, rate_limit, expires_at)
            )
            conn.commit()

            cursor = conn.execute("SELECT LAST_INSERT_ID() as id")
            key_id = cursor.fetchone()['id']

            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE id = %s",
                (key_id,)
            )
            return ApiKey(**cursor.fetchone()), plain_key

    @staticmethod
    def get_by_id(key_id: int) -> Optional[ApiKey]:
        """Get API key by ID.

        Args:
            key_id: API key ID

        Returns:
            ApiKey object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE id = %s",
                (key_id,)
            )
            row = cursor.fetchone()
            if row:
                return ApiKey(**row)
            return None

    @staticmethod
    def get_by_hash(api_key_hash: str) -> Optional[ApiKey]:
        """Get API key by hash.

        Args:
            api_key_hash: Hashed API key

        Returns:
            ApiKey object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_keys WHERE api_key_hash = %s AND status = 'active'",
                (api_key_hash,)
            )
            row = cursor.fetchone()
            if row:
                # Check expiration
                if row['expires_at'] and row['expires_at'] < datetime.now():
                    return None
                return ApiKey(**row)
            return None

    @staticmethod
    def verify(plain_key: str) -> Optional[ApiKey]:
        """Verify an API key.

        Args:
            plain_key: Plain text API key

        Returns:
            ApiKey object if valid, None otherwise
        """
        hashed_key = hash_api_key(plain_key)
        return ApiKeyRepository.get_by_hash(hashed_key)

    @staticmethod
    def update_last_used(key_id: int) -> None:
        """Update last used timestamp.

        Args:
            key_id: API key ID
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE api_keys SET last_used_at = %s WHERE id = %s",
                (datetime.now(), key_id)
            )
            conn.commit()

    @staticmethod
    def get_by_user(user_id: int) -> List[ApiKey]:
        """Get all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of ApiKey objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM api_keys
                   WHERE user_id = %s
                   ORDER BY created_at DESC""",
                (user_id,)
            )
            return [ApiKey(**row) for row in cursor.fetchall()]

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> List[ApiKey]:
        """List all API keys.

        Args:
            limit: Max results
            offset: Result offset

        Returns:
            List of ApiKey objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM api_keys
                   ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (limit, offset)
            )
            return [ApiKey(**row) for row in cursor.fetchall()]

    @staticmethod
    def toggle_status(key_id: int) -> bool:
        """Toggle API key status.

        Args:
            key_id: API key ID

        Returns:
            New status (True if active, False if disabled)
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT status FROM api_keys WHERE id = %s",
                (key_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            new_status = "disabled" if row['status'] == "active" else "active"
            conn.execute(
                "UPDATE api_keys SET status = %s WHERE id = %s",
                (new_status, key_id)
            )
            conn.commit()
            return new_status == "active"

    @staticmethod
    def delete(key_id: int) -> bool:
        """Delete an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deleted
        """
        with get_connection() as conn:
            conn.execute("DELETE FROM api_keys WHERE id = %s", (key_id,))
            conn.commit()
            return True

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get API key statistics.

        Returns:
            Dict with usage statistics
        """
        with get_connection() as conn:
            # Total keys
            cursor = conn.execute("SELECT COUNT(*) as count FROM api_keys")
            total = cursor.fetchone()['count']

            # Active keys
            cursor = conn.execute("SELECT COUNT(*) as count FROM api_keys WHERE status = 'active'")
            active = cursor.fetchone()['count']

            # Keys used today
            cursor = conn.execute(
                """SELECT COUNT(*) as count FROM api_keys
                   WHERE last_used_at >= CURDATE()"""
            )
            used_today = cursor.fetchone()['count']

            return {
                "total": total,
                "active": active,
                "used_today": used_today,
            }
