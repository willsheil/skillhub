"""Users business logic services."""

from typing import List, Optional, Dict, Any
import secrets


# Import database functions - will be imported from database module
def get_connection():
    """Database connection context manager."""
    from database import get_connection as _get_connection
    return _get_connection()


def get_user_by_credentials(employee_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Query user by employee ID and API key.

    Args:
        employee_id: The employee's ID
        api_key: The API key for authentication

    Returns:
        User dictionary if found and enabled, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, employee_id, api_key, role, created_at, last_login, status
            FROM users
            WHERE employee_id = %s AND api_key = %s
            """,
            (employee_id, api_key)
        ).fetchone()

        if row:
            # Check if user is disabled
            if row.get("status") == "disabled":
                return None
            return {
                "id": row["id"],
                "employee_id": row["employee_id"],
                "api_key": row["api_key"],
                "role": row["role"],
                "created_at": row["created_at"],
                "last_login": row["last_login"],
                "status": row["status"]
            }
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Query user by ID.

    Args:
        user_id: The user's ID

    Returns:
        User dictionary if found, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, employee_id, api_key, role, status, skills_count, created_at, last_login
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "employee_id": row["employee_id"],
                "api_key": row["api_key"],
                "role": row["role"],
                "status": row["status"],
                "skills_count": row["skills_count"],
                "created_at": row["created_at"],
                "last_login": row["last_login"]
            }
        return None


def update_last_login(user_id: int) -> None:
    """Update the last login timestamp for a user.

    Args:
        user_id: The user's ID
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (user_id,)
        )
        conn.commit()


def create_user(employee_id: str, api_key: str, role: str = "user") -> int:
    """Create a new user in system.

    Args:
        employee_id: The employee's unique ID
        api_key: The API key for authentication
        role: User role ('user' or 'admin')

    Returns:
        The ID of the created user
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role)
            VALUES (%s, %s, %s)
            """,
            (employee_id, api_key, role)
        )
        conn.commit()
        return cursor.lastrowid


def get_users_list(
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
        Dictionary containing:
        - users: List of user records
        - total: Total count matching filter
        - page: Current page number
        - per_page: Items per page
        - pages: Total number of pages
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

    with get_connection() as conn:
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


def update_user_role(user_id: int, role: str) -> bool:
    """Update a user's role.

    Args:
        user_id: The user's ID
        role: New role ('admin' or 'user')

    Returns:
        True if updated, False if user not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET role = %s
            WHERE id = %s
            """,
            (role, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def disable_user(user_id: int) -> bool:
    """Disable a user (soft delete).

    Args:
        user_id: The user's ID

    Returns:
        True if disabled, False if user not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET status = 'disabled'
            WHERE id = %s
            """,
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def enable_user(user_id: int) -> bool:
    """Re-enable a disabled user.

    Args:
        user_id: The user's ID

    Returns:
        True if enabled, False if user not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET status = 'active'
            WHERE id = %s
            """,
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_user(user_id: int) -> bool:
    """Permanently delete a user.

    Args:
        user_id: The user's ID

    Returns:
        True if deleted, False if user not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def reset_user_api_key(user_id: int, new_api_key: str) -> bool:
    """Reset a user's API key.

    Args:
        user_id: The user's ID
        new_api_key: The new API key

    Returns:
        True if updated, False if user not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE users
            SET api_key = %s
            WHERE id = %s
            """,
            (new_api_key, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def generate_api_key() -> str:
    """Generate a secure random API key.

    Returns:
        A 32-character hexadecimal string
    """
    return secrets.token_hex(16)
