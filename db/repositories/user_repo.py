"""
User repository - Database operations for users.

Provides methods for user CRUD operations, authentication, and user management.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from db.connection import get_connection
from db.models import User
from core.constants import UserRole
from core.security import hash_api_key, generate_api_key

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user database operations."""

    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return User(**row)
            return None

    @staticmethod
    def get_by_employee_id(employee_id: str) -> Optional[User]:
        """Get user by employee ID.

        Args:
            employee_id: Employee ID

        Returns:
            User object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE employee_id = %s",
                (employee_id,)
            )
            row = cursor.fetchone()
            if row:
                return User(**row)
            return None

    @staticmethod
    def get_by_credentials(employee_id: str, api_key: str) -> Optional[User]:
        """Authenticate user by employee ID and API key.

        Args:
            employee_id: Employee ID
            api_key: Plain text API key

        Returns:
            User object if credentials valid, None otherwise
        """
        hashed_key = hash_api_key(api_key)
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE employee_id = %s AND api_key = %s AND status = 'active'",
                (employee_id, hashed_key)
            )
            row = cursor.fetchone()
            if row:
                return User(**row)
            return None

    @staticmethod
    def create(employee_id: str, api_key: str, role: str = UserRole.USER.value) -> User:
        """Create a new user.

        Args:
            employee_id: Employee ID
            api_key: Plain text API key (will be hashed)
            role: User role (default: user)

        Returns:
            Created User object

        Raises:
            Exception: If user already exists
        """
        hashed_key = hash_api_key(api_key)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (%s, %s, %s)",
                (employee_id, hashed_key, role)
            )
            conn.commit()

            # Get the created user
            cursor = conn.execute(
                "SELECT * FROM users WHERE employee_id = %s",
                (employee_id,)
            )
            row = cursor.fetchone()
            return User(**row)

    @staticmethod
    def update_last_login(user_id: int) -> None:
        """Update user's last login timestamp.

        Args:
            user_id: User ID
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (datetime.now(), user_id)
            )
            conn.commit()

    @staticmethod
    def update_role(user_id: int, role: str) -> None:
        """Update user's role.

        Args:
            user_id: User ID
            role: New role
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET role = %s WHERE id = %s",
                (role, user_id)
            )
            conn.commit()

    @staticmethod
    def update_status(user_id: int, status: str) -> None:
        """Update user's status.

        Args:
            user_id: User ID
            status: New status (active/disabled)
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET status = %s WHERE id = %s",
                (status, user_id)
            )
            conn.commit()

    @staticmethod
    def reset_api_key(user_id: int) -> str:
        """Reset user's API key.

        Args:
            user_id: User ID

        Returns:
            New API key (plain text)
        """
        new_key = generate_api_key()
        hashed_key = hash_api_key(new_key)
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET api_key = %s WHERE id = %s",
                (hashed_key, user_id)
            )
            conn.commit()
        return new_key

    @staticmethod
    def increment_skills_count(user_id: int) -> None:
        """Increment user's skills count.

        Args:
            user_id: User ID
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET skills_count = skills_count + 1 WHERE id = %s",
                (user_id,)
            )
            conn.commit()

    @staticmethod
    def decrement_skills_count(user_id: int) -> None:
        """Decrement user's skills count.

        Args:
            user_id: User ID
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET skills_count = GREATEST(skills_count - 1, 0) WHERE id = %s",
                (user_id,)
            )
            conn.commit()

    @staticmethod
    def get_skills_count(user_id: int) -> int:
        """Get user's skills count.

        Args:
            user_id: User ID

        Returns:
            Number of skills uploaded by user
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT skills_count FROM users WHERE id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            return row['skills_count'] if row else 0

    @staticmethod
    def list_users(role: Optional[str] = None, status: Optional[str] = None,
                   limit: int = 100, offset: int = 0) -> List[User]:
        """List users with optional filters.

        Args:
            role: Filter by role
            status: Filter by status
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of User objects
        """
        conditions = []
        params = []

        if role:
            conditions.append("role = %s")
            params.append(role)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        with get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM users WHERE {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params
            )
            return [User(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_total_count(role: Optional[str] = None, status: Optional[str] = None) -> int:
        """Get total number of users.

        Args:
            role: Filter by role
            status: Filter by status

        Returns:
            Total count
        """
        conditions = []
        params = []

        if role:
            conditions.append("role = %s")
            params.append(role)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with get_connection() as conn:
            cursor = conn.execute(
                f"SELECT COUNT(*) as count FROM users WHERE {where_clause}",
                params
            )
            return cursor.fetchone()['count']

    @staticmethod
    def delete(user_id: int) -> bool:
        """Delete a user.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if not found
        """
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return conn.execute("SELECT ROW_COUNT()").fetchone()['ROW_COUNT()'] > 0
