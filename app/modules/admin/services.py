"""
Admin module business logic services.

Provides core admin functionality for user management and statistics.
"""

import logging
import secrets
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Get logger for this module
logger = logging.getLogger("skillhub.admin.services")


class AdminService:
    """Service class for admin operations."""

    def __init__(self, db_module):
        """Initialize admin service with database module.

        Args:
            db_module: The database module with connection functions
        """
        self.db = db_module

    def get_users_list(
        self,
        page: int = 1,
        per_page: int = 20,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of users with optional filters.

        Args:
            page: Page number (1-indexed)
            per_page: Number of users per page
            role: Filter by role ('admin' or 'user')
            status_filter: Filter by status ('active' or 'disabled')
            search: Search by employee_id (partial match)

        Returns:
            Dictionary containing users, total, page, per_page, pages
        """
        # Validate inputs against whitelist to prevent SQL injection
        valid_roles = {'admin', 'user'}
        valid_statuses = {'active', 'disabled'}

        if role is not None and role not in valid_roles:
            raise ValueError(f"Invalid role: {role}. Must be one of {valid_roles}")

        if status_filter is not None and status_filter not in valid_statuses:
            raise ValueError(f"Invalid status_filter: {status_filter}. Must be one of {valid_statuses}")

        # Build WHERE clause
        conditions = []
        params = []

        if role:
            conditions.append("role = %s")
            params.append(role)

        if status_filter:
            conditions.append("status = %s")
            params.append(status_filter)

        if search:
            conditions.append("employee_id LIKE %s")
            params.append(f"%{search}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        with self.db.get_connection() as conn:
            # Get total count
            total_row = conn.execute(
                f"SELECT COUNT(*) as total FROM users{where_clause}",
                params
            ).fetchone()
            total = total_row["total"] if total_row else 0

            # Get paginated results
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""
                SELECT id, employee_id, role, status, skills_count, created_at, last_login
                FROM users
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [per_page, offset]
            ).fetchall()

            users = []
            for row in rows:
                users.append({
                    "id": row["id"],
                    "employee_id": row["employee_id"],
                    "role": row["role"],
                    "status": row["status"],
                    "skills_count": row["skills_count"],
                    "created_at": row["created_at"],
                    "last_login": row["last_login"]
                })

            pages = (total + per_page - 1) // per_page if total > 0 else 1

            return {
                "users": users,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": pages
            }

    def create_user(self, employee_id: str, role: str) -> Dict[str, Any]:
        """Create a new user with generated API key.

        Args:
            employee_id: Employee ID
            role: User role ('admin' or 'user')

        Returns:
            Dictionary with created user data and API key

        Raises:
            ValueError: If employee_id already exists
        """
        # Check if user exists
        existing_user = self.db.get_user_by_credentials(employee_id, "dummy")
        if existing_user:
            raise ValueError(f"User with employee_id '{employee_id}' already exists")

        # Generate 32-char API key
        api_key = secrets.token_hex(16)

        # Create user
        user_id = self.db.create_user(
            employee_id=employee_id,
            api_key=api_key,
            role=role
        )

        # Get the created user
        user = self.db.get_user_by_id(user_id)

        return {
            "id": user["id"],
            "employee_id": user["employee_id"],
            "role": user["role"],
            "api_key": api_key,
            "created_at": user["created_at"]
        }

    def update_user_role(self, user_id: int, role: str) -> bool:
        """Update a user's role.

        Args:
            user_id: The user's ID
            role: New role ('admin' or 'user')

        Returns:
            True if updated, False if user not found
        """
        return self.db.update_user_role(user_id, role)

    def disable_user(self, user_id: int) -> bool:
        """Disable a user (soft delete).

        Args:
            user_id: The user's ID

        Returns:
            True if disabled, False if user not found
        """
        return self.db.disable_user(user_id)

    def enable_user(self, user_id: int) -> bool:
        """Re-enable a disabled user.

        Args:
            user_id: The user's ID

        Returns:
            True if enabled, False if user not found
        """
        return self.db.enable_user(user_id)

    def delete_user(self, user_id: int) -> bool:
        """Permanently delete a user.

        Args:
            user_id: The user's ID

        Returns:
            True if deleted, False if user not found
        """
        return self.db.delete_user(user_id)

    def reset_user_api_key(self, user_id: int, new_api_key: str) -> bool:
        """Reset a user's API key.

        Args:
            user_id: The user's ID
            new_api_key: The new API key

        Returns:
            True if updated, False if user not found
        """
        return self.db.reset_user_api_key(user_id, new_api_key)

    def get_admin_stats(self) -> Dict[str, Any]:
        """Get comprehensive admin statistics.

        Returns:
            Dictionary with total_users, pending_skills, approved_skills,
            today_downloads, top_skills, top_users
        """
        total_users = self.db.get_total_users_count()
        pending_skills = self.db.get_skills_count_by_status("pending")
        approved_skills = self.db.get_skills_count_by_status("approved")
        today_downloads = self.db.get_today_downloads_count()
        top_skills = self.db.get_top_skills_by_downloads(10)
        top_users = self.db.get_top_users_by_downloads(10)

        return {
            "total_users": total_users,
            "pending_skills": pending_skills,
            "approved_skills": approved_skills,
            "today_downloads": today_downloads,
            "top_skills": top_skills,
            "top_users": top_users
        }


class ApiKeyRateLimiter:
    """Rate limiter for API key reset operations."""

    def __init__(self, rate_limit_minutes: int = 5):
        """Initialize rate limiter.

        Args:
            rate_limit_minutes: Minutes between allowed operations
        """
        self.rate_limit_minutes = rate_limit_minutes
        self._reset_times: Dict[int, datetime] = {}

    def check_rate_limit(self, user_id: int) -> Optional[str]:
        """Check if operation is allowed for user.

        Args:
            user_id: The user ID to check

        Returns:
            Error message if rate limited, None otherwise
        """
        current_time = datetime.now()

        if user_id in self._reset_times:
            last_reset_time = self._reset_times[user_id]
            time_since_reset = current_time - last_reset_time
            if time_since_reset < timedelta(minutes=self.rate_limit_minutes):
                return (f"API key reset too frequently. "
                       f"Please wait {self.rate_limit_minutes} minutes between resets.")

        return None

    def record_operation(self, user_id: int) -> None:
        """Record that an operation occurred for user.

        Args:
            user_id: The user ID
        """
        self._reset_times[user_id] = datetime.now()
