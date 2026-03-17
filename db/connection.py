"""
Database connection management for SkillHub.

Provides:
- Connection wrapper for PyMySQL
- Database configuration
- Connection context manager
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional
import pymysql
from pymysql.cursors import DictCursor

from core.config import get_settings
from core.constants import SkillStatus, SourceType

logger = logging.getLogger(__name__)


class ConnectionWrapper:
    """Wrapper to provide execute() method on PyMySQL connections.

    PyMySQL doesn't support conn.execute() directly, requiring cursor.execute().
    This wrapper provides compatibility with code that expects execute() on the connection.
    """

    def __init__(self, conn: pymysql.Connection):
        """Initialize wrapper with a PyMySQL connection.

        Args:
            conn: PyMySQL connection object
        """
        self._conn = conn

    def execute(self, query: str, params: Optional[tuple] = None):
        """Execute a query using a cursor.

        Args:
            query: SQL query string
            params: Optional parameters for the query

        Returns:
            Cursor object with results
        """
        cursor = self._conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def commit(self) -> None:
        """Commit the current transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    @property
    def cursor(self):
        """Get a new cursor."""
        return self._conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()

    def __getattr__(self, name: str):
        """Delegate all other attributes to the underlying connection."""
        return getattr(self._conn, name)


@contextmanager
def get_connection() -> Generator[ConnectionWrapper, None, None]:
    """Get a database connection from the pool.

    Yields:
        ConnectionWrapper: Wrapped database connection

    Example:
        >>> with get_connection() as conn:
        ...     cursor = conn.execute("SELECT * FROM users")
        ...     print(cursor.fetchall())
    """
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_DATABASE,
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False,
    )
    yield ConnectionWrapper(conn)
    conn.close()


def create_connection() -> ConnectionWrapper:
    """Create a new database connection.

    Returns:
        ConnectionWrapper: New database connection

    Note:
        Caller is responsible for closing the connection.
    """
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_DATABASE,
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False,
    )
    return ConnectionWrapper(conn)


def init_db() -> None:
    """Initialize database and create tables if they don't exist.

    Creates the following tables:
    - users
    - skills
    - downloads
    - notifications
    - gitea_push_tasks
    - api_keys
    """
    settings = get_settings()

    # First connect without database to create it if needed
    conn = pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        charset='utf8mb4',
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.DB_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    finally:
        conn.close()

    # Now connect to the database and create tables
    with get_connection() as db:
        # Users table
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id VARCHAR(20) UNIQUE NOT NULL,
                api_key VARCHAR(64) NOT NULL,
                role VARCHAR(10) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                skills_count INT DEFAULT 0,
                last_login TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_employee_id (employee_id),
                INDEX idx_api_key (api_key),
                INDEX idx_role (role)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Skills table
        db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                skill_name VARCHAR(64) NOT NULL,
                version VARCHAR(20) NOT NULL,
                filename VARCHAR(128) NOT NULL,
                description TEXT,
                metadata JSON,
                uploader_id INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                source_type VARCHAR(20) NOT NULL DEFAULT 'opensource',
                is_active TINYINT(1) DEFAULT 1,
                is_default_version TINYINT(1) DEFAULT 0,
                latest_push_task_id INT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP NULL,
                reviewer_id INT NULL,
                review_comment VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_skill_version (skill_name, version),
                INDEX idx_skill_name (skill_name),
                INDEX idx_uploader_id (uploader_id),
                INDEX idx_status (status),
                INDEX idx_source_type (source_type),
                FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Downloads table
        db.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INT AUTO_INCREMENT PRIMARY KEY,
                skill_name VARCHAR(64) NOT NULL,
                version VARCHAR(20) NOT NULL,
                user_id INT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_skill_name (skill_name),
                INDEX idx_downloaded_at (downloaded_at),
                INDEX idx_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Notifications table
        db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                type VARCHAR(20) NOT NULL,
                title VARCHAR(128) NOT NULL,
                content TEXT,
                related_skill_id INT,
                is_read TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_is_read (is_read),
                INDEX idx_created_at (created_at),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (related_skill_id) REFERENCES skills(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Gitea push tasks table
        db.execute("""
            CREATE TABLE IF NOT EXISTS gitea_push_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                skill_id INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                retry_count INT DEFAULT 0,
                worker_id VARCHAR(64),
                commit_hash VARCHAR(40),
                error_message TEXT,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_skill_id (skill_id),
                INDEX idx_status (status),
                INDEX idx_worker_id (worker_id),
                FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # API Keys table
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                key_name VARCHAR(64) NOT NULL,
                api_key_hash VARCHAR(64) NOT NULL,
                user_id INT NOT NULL,
                rate_limit INT DEFAULT 100,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                last_used_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                INDEX idx_api_key_hash (api_key_hash),
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        db.commit()
        logger.info("Database initialized successfully")
