"""
Database configuration and connection management.

This module provides:
- Database connection configuration
- Database initialization
- Connection management
- Migration functions
"""

import os
import logging
import pymysql
from contextlib import contextmanager

# Get logger for this module
logger = logging.getLogger("skillhub.database.config")

DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'database': os.getenv('DB_DATABASE', 'skills'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}


class ConnectionWrapper:
    """Wrapper to provide execute() method on PyMySQL connections.

    PyMySQL doesn't support conn.execute() directly, requiring cursor.execute().
    This wrapper provides compatibility with code that expects execute() on the connection.
    """

    def __init__(self, conn):
        """Initialize wrapper with a PyMySQL connection.

        Args:
            conn: PyMySQL connection object
        """
        self._conn = conn

    def execute(self, query, params=None):
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

    def commit(self):
        """Commit the current transaction."""
        self._conn.commit()

    def __getattr__(self, name):
        """Delegate all other attributes to the underlying connection.

        Args:
            name: Attribute name

        Returns:
            Attribute from the underlying connection
        """
        return getattr(self._conn, name)


def create_index_if_not_exists(cursor, table_name, index_name, index_definition):
    """Create an index if it doesn't exist.

    This function provides MySQL-compatible index creation by checking
    information_schema.statistics first, since MySQL doesn't support
    CREATE INDEX IF NOT EXISTS syntax.

    Args:
        cursor: Database cursor object
        table_name: Name of the table
        index_name: Name of the index to create
        index_definition: Full CREATE INDEX SQL statement
    """
    cursor.execute("""
        SELECT COUNT(*) as count FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s
    """, (table_name, index_name))

    if cursor.fetchone()['count'] == 0:
        cursor.execute(index_definition)


def migrate_add_user_id_to_downloads():
    """Migrate downloads table to add user_id column if it doesn't exist.

    This should be called AFTER the downloads table is created to ensure
    the table exists before attempting to add the column.
    """
    from app.core.database.models import get_connection

    with get_connection() as conn:
        # Check if user_id column already exists using DESCRIBE
        cursor = conn.execute("DESCRIBE downloads")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "user_id" not in columns:
            conn.execute("ALTER TABLE downloads ADD COLUMN user_id INT")
            conn.commit()
            logger.info("Migration: Added user_id column to downloads table")
        else:
            logger.info("Migration: user_id column already exists in downloads table")


def migrate_add_source_type_to_skills():
    """Migrate skills table to add source_type column if it doesn't exist.

    Source type can be: 'opensource', 'icsl', 'huawei'
    """
    from app.core.database.models import get_connection

    with get_connection() as conn:
        cursor = conn.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "source_type" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN source_type VARCHAR(20) DEFAULT 'opensource'")
            conn.commit()
            logger.info("Migration: Added source_type column to skills table")
        else:
            logger.info("Migration: source_type column already exists in skills table")


def migrate_table_engines():
    """Migrate existing tables to InnoDB engine for foreign key support."""
    from app.core.database.models import get_connection

    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # Check and convert users table
        cursor.execute("""
            SELECT ENGINE FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'
        """)
        result = cursor.fetchone()
        if result and result.get('ENGINE') != 'InnoDB':
            conn.execute("ALTER TABLE users ENGINE=InnoDB")
            conn.commit()
            logger.info("Migration: Converted users table to InnoDB")

        # Check and convert skills table
        cursor.execute("""
            SELECT ENGINE FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'skills'
        """)
        result = cursor.fetchone()
        if result and result.get('ENGINE') != 'InnoDB':
            conn.execute("ALTER TABLE skills ENGINE=InnoDB")
            conn.commit()
            logger.info("Migration: Converted skills table to InnoDB")

        # Check and convert downloads table
        cursor.execute("""
            SELECT ENGINE FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'downloads'
        """)
        result = cursor.fetchone()
        if result and result.get('ENGINE') != 'InnoDB':
            conn.execute("ALTER TABLE downloads ENGINE=InnoDB")
            conn.commit()
            logger.info("Migration: Converted downloads table to InnoDB")


def migrate_gitea_push_tasks():
    """Migrate database to add gitea_push_tasks table and skills.latest_push_task_id column.

    Creates gitea_push_tasks table for tracking async push operations
    and adds a foreign key column to skills table for tracking latest
    push task. This should be called AFTER skills table is created.

    Enhanced state machine includes:
    - 'pending': Task is waiting to be processed
    - 'reserved': Task has been reserved by a worker (prevents duplicate processing)
    - 'pushing': Task is actively being pushed
    - 'success': Task completed successfully
    - 'failed': Task failed (may or may not be retryable)
    - 'retry_pending': Task failed and is waiting for retry
    """
    from app.core.database.models import get_connection

    with get_connection() as conn:
        # Drop table first if it exists to ensure clean schema
        conn.execute("DROP TABLE IF EXISTS gitea_push_tasks")
        conn.commit()

        conn.execute("""
            CREATE TABLE gitea_push_tasks (
                id INT PRIMARY KEY AUTO_INCREMENT,
                skill_id INT NOT NULL,
                skill_name VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                status ENUM('pending', 'reserved', 'pushing', 'success', 'failed', 'retry_pending') DEFAULT 'pending',
                retry_count INT DEFAULT 0,
                max_retries INT DEFAULT 3,
                error_message TEXT,
                commit_hash VARCHAR(40),
                gitea_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reserved_at TIMESTAMP NULL,
                worker_id VARCHAR(50) NULL,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (skill_id) REFERENCES skills(id),
                INDEX idx_status_created (status, created_at),
                INDEX idx_worker_reserved (worker_id, reserved_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
        logger.info("Migration: gitea_push_tasks table created with enhanced state machine")

        # Add column to skills table if not exists
        cursor = conn._conn.cursor()
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "latest_push_task_id" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN latest_push_task_id INT NULL")
            conn.commit()
            logger.info("Migration: Added latest_push_task_id column to skills table")
        else:
            logger.info("Migration: latest_push_task_id column already exists in skills table")


def migrate_gitea_reserved_status():
    """Migrate existing gitea_push_tasks table to add reserved status support.

    Adds new columns for task reservation:
    - reserved_at: Timestamp when task was reserved
    - worker_id: ID of worker that reserved task

    This migration can be run on existing installations to add new
    state machine features without losing existing data.
    """
    from app.core.database.models import get_connection

    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # Check current table structure
        cursor.execute("DESCRIBE gitea_push_tasks")
        columns = [row["Field"] for row in cursor.fetchall()]

        # Add reserved_at column
        if "reserved_at" not in columns:
            conn.execute("ALTER TABLE gitea_push_tasks ADD COLUMN reserved_at TIMESTAMP NULL AFTER created_at")
            conn.commit()
            logger.info("Migration: Added reserved_at column to gitea_push_tasks table")
        else:
            logger.info("Migration: reserved_at column already exists in gitea_push_tasks table")

        # Add worker_id column
        if "worker_id" not in columns:
            conn.execute("ALTER TABLE gitea_push_tasks ADD COLUMN worker_id VARCHAR(50) NULL AFTER reserved_at")
            conn.commit()
            logger.info("Migration: Added worker_id column to gitea_push_tasks table")
        else:
            logger.info("Migration: worker_id column already exists in gitea_push_tasks table")

        # Update ENUM to include new statuses
        # MySQL doesn't support modifying ENUM directly, need to recreate
        logger.info("Migration: Status enum expansion requires manual recreation or use migrate_gitea_push_tasks()")
        logger.info("  For new installations, full schema includes: pending, reserved, pushing, success, failed, retry_pending")


def migrate_add_user_management_features():
    """Migrate database to add user management and notification features.

    Adds columns:
    - users.status (default 'active')
    - users.skills_count (default 0)
    - skills.is_active (default 1)
    - skills.is_default_version (default 0)

    Creates notifications table with indexes.
    """
    from app.core.database.models import get_connection

    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # Add status column to users table
        cursor.execute("DESCRIBE users")
        columns = [row["Field"] for row in cursor.fetchall()]
        if "status" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'active'")
            conn.commit()
            logger.info("Migration: Added status column to users table")

        # Add skills_count column to users table
        cursor.execute("DESCRIBE users")
        columns = [row["Field"] for row in cursor.fetchall()]
        if "skills_count" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN skills_count INT DEFAULT 0")
            conn.commit()
            logger.info("Migration: Added skills_count column to users table")

        # Add is_active column to skills table
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]
        if "is_active" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN is_active TINYINT(1) DEFAULT 1")
            conn.commit()
            logger.info("Migration: Added is_active column to skills table")

        # Add is_default_version column to skills table
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]
        if "is_default_version" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN is_default_version TINYINT(1) DEFAULT 0")
            conn.commit()
            logger.info("Migration: Added is_default_version column to skills table")

        # Create notifications table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT,
                related_skill_id INT,
                is_read TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (related_skill_id) REFERENCES skills(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()

        # Create indexes for notifications
        create_index_if_not_exists(
            cursor,
            "notifications",
            "idx_notifications_user_unread",
            "CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read)"
        )
        create_index_if_not_exists(
            cursor,
            "notifications",
            "idx_notifications_user_created",
            "CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at DESC)"
        )

        # Create indexes for users table
        create_index_if_not_exists(
            cursor,
            "users",
            "idx_users_status",
            "CREATE INDEX idx_users_status ON users(status)"
        )
        create_index_if_not_exists(
            cursor,
            "users",
            "idx_users_status_role",
            "CREATE INDEX idx_users_status_role ON users(status, role)"
        )

        # Create indexes for skills table
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skills_is_active",
            "CREATE INDEX idx_skills_is_active ON skills(is_active)"
        )
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skills_uploader_active",
            "CREATE INDEX idx_skills_uploader_active ON skills(uploader_id, is_active)"
        )

        logger.info("Migration: user_management_features migration completed")


@contextmanager
def get_connection():
    """Get database connection context manager."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield ConnectionWrapper(conn)
    finally:
        conn.close()


def init_db():
    """Initialize database and create tables."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INT PRIMARY KEY AUTO_INCREMENT,
                skill_name VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(255),
                user_agent VARCHAR(255),
                user_id INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Index for faster queries
        cursor = conn._conn.cursor()
        create_index_if_not_exists(
            cursor,
            "downloads",
            "idx_downloads_skill_date",
            "CREATE INDEX idx_downloads_skill_date ON downloads(skill_name, downloaded_at)"
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                employee_id VARCHAR(20) UNIQUE NOT NULL,
                api_key VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) DEFAULT 'active',
                skills_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Index for employee_id lookups
        cursor = conn._conn.cursor()
        create_index_if_not_exists(
            cursor,
            "users",
            "idx_users_employee_id",
            "CREATE INDEX idx_users_employee_id ON users(employee_id)"
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INT PRIMARY KEY AUTO_INCREMENT,
                skill_name VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                uploader_id INT NOT NULL,
                status VARCHAR(20),
                source_type VARCHAR(20) DEFAULT 'opensource',
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP NULL,
                reviewer_id INT,
                review_comment VARCHAR(255),
                FOREIGN KEY (uploader_id) REFERENCES users(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # Index for status lookups
        cursor = conn._conn.cursor()
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skills_status",
            "CREATE INDEX idx_skills_status ON skills(status)"
        )

        # Index for uploader lookups
        cursor = conn._conn.cursor()
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skills_uploader",
            "CREATE INDEX idx_skills_uploader ON skills(uploader_id)"
        )

        conn.commit()

    # Run migrations after all tables are created
    migrate_table_engines()  # Convert existing tables to InnoDB for foreign key support
    migrate_add_user_id_to_downloads()
    migrate_gitea_push_tasks()
    migrate_add_source_type_to_skills()
    migrate_add_user_management_features()


__all__ = [
    "DB_CONFIG",
    "ConnectionWrapper",
    "create_index_if_not_exists",
    "migrate_add_user_id_to_downloads",
    "migrate_add_source_type_to_skills",
    "migrate_table_engines",
    "migrate_gitea_push_tasks",
    "migrate_gitea_reserved_status",
    "migrate_add_user_management_features",
    "get_connection",
    "init_db",
]
