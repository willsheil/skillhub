"""
Database module for download statistics.
"""

import os
import pymysql
import json
import logging
import secrets
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

# Get logger for this module
logger = logging.getLogger("skillhub.database")

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
    with get_connection() as conn:
        cursor = conn.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "source_type" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN source_type VARCHAR(20) DEFAULT 'opensource'")
            conn.commit()
            logger.info("Migration: Added source_type column to skills table")
        else:
            logger.info("Migration: source_type column already exists in skills table")


def migrate_add_review_fields_to_skills():
    """Migrate skills table to add review-related columns if they don't exist.

    Adds: uploaded_at, reviewed_at, reviewer_id, review_comment
    """
    with get_connection() as conn:
        cursor = conn.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        fields_to_add = [
            ("uploaded_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("reviewed_at", "TIMESTAMP NULL"),
            ("reviewer_id", "INT NULL"),
            ("review_comment", "VARCHAR(255) NULL"),
        ]

        for field_name, field_type in fields_to_add:
            if field_name not in columns:
                conn.execute(f"ALTER TABLE skills ADD COLUMN {field_name} {field_type}")
                conn.commit()
                logger.info(f"Migration: Added {field_name} column to skills table")
            else:
                logger.info(f"Migration: {field_name} column already exists in skills table")


def migrate_table_engines():
    """Migrate existing tables to InnoDB engine for foreign key support."""
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
                status VARCHAR(20) DEFAULT 'pending',
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
    migrate_add_review_fields_to_skills()  # Add uploaded_at, reviewed_at, reviewer_id, review_comment
    migrate_add_user_management_features()
    migrate_add_skill_description_and_metadata()
    migrate_to_single_version()
    init_external_api_tables()  # 创建外部 API 相关表
    # 新增：评分评论、搜索、分类系统
    migrate_add_rating_comment_system()
    migrate_add_search_features()
    migrate_add_category_system()
    # 新增：用户档案字段
    migrate_add_user_profile_fields()
    # 新增：用户信息字段
    migrate_add_user_profile_fields()


def migrate_gitea_push_tasks():
    """Migrate database to add gitea_push_tasks table and skills.latest_push_task_id column.

    Creates the gitea_push_tasks table for tracking async push operations
    and adds a foreign key column to the skills table for tracking the latest
    push task. This should be called AFTER the skills table is created.

    Enhanced state machine includes:
    - 'pending': Task is waiting to be processed
    - 'reserved': Task has been reserved by a worker (prevents duplicate processing)
    - 'pushing': Task is actively being pushed
    - 'success': Task completed successfully
    - 'failed': Task failed (may or may not be retryable)
    - 'retry_pending': Task failed and is waiting for retry
    """
    with get_connection() as conn:
        # Drop the table first if it exists to ensure clean schema
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
    - worker_id: ID of the worker that reserved the task

    This migration can be run on existing installations to add the new
    state machine features without losing existing data.
    """
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
        logger.info("  For new installations, the full schema includes: pending, reserved, pushing, success, failed, retry_pending")


def migrate_add_user_profile_fields():
    """Migrate users table to add profile fields if they don't exist.

    Adds: name, minDepartment, team, group
    """
    with get_connection() as conn:
        cursor = conn._conn.cursor()
        cursor.execute("DESCRIBE users")
        columns = [row["Field"] for row in cursor.fetchall()]

        fields_to_add = [
            ("name", "VARCHAR(100) NULL"),
            ("minDepartment", "VARCHAR(100) NULL"),
            ("team", "VARCHAR(100) NULL"),
            ("group", "VARCHAR(100) NULL"),
        ]

        for field_name, field_type in fields_to_add:
            if field_name not in columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {field_name} {field_type}")
                conn.commit()
                logger.info(f"Migration: Added {field_name} column to users table")
            else:
                logger.info(f"Migration: {field_name} column already exists in users table")


@contextmanager
def get_connection():
    """Get database connection context manager."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield ConnectionWrapper(conn)
    finally:
        conn.close()


def record_download(
    skill_name: str,
    version: str,
    filename: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_id: Optional[int] = None
) -> int:
    """Record a download event.

    Args:
        skill_name: The name of the skill being downloaded
        version: The version of the skill
        filename: The filename being downloaded
        ip_address: Optional IP address of the downloader
        user_agent: Optional user agent string
        user_id: Optional user ID if authenticated

    Returns:
        The ID of the inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO downloads (skill_name, version, filename, ip_address, user_agent, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (skill_name, version, filename, ip_address, user_agent, user_id)
        )
        conn.commit()
        return cursor.lastrowid


def get_download_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """Get download statistics for a date range.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today
        days: Number of days for range (default 30), max 90

    Returns:
        {
            "total_downloads": int,
            "rankings": [
                {"skill_name": str, "author": str, "downloads": int},
                ...
            ]
        }
    """
    # Default to last 30 days if no dates provided
    if start_date is None and end_date is None:
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

    # Override end_date if days is specified
    if days is not None:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

    with get_connection() as conn:
        # Get total downloads
        total_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE DATE(downloaded_at) BETWEEN %s AND %s
            """,
            (start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total_downloads = total_row["total"] if total_row else 0

        # Get rankings by skill (limited to top 6)
        rankings = []
        rows = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as download_count
            FROM downloads
            WHERE DATE(downloaded_at) BETWEEN %s AND %s
            GROUP BY skill_name
            ORDER BY download_count DESC
            LIMIT 6
            """,
            (start_date.isoformat(), end_date.isoformat())
        ).fetchall()

        for row in rows:
            rankings.append({
                "skill_name": row["skill_name"],
                "downloads": row["download_count"]
            })

        return {
            "total_downloads": total_downloads,
            "rankings": rankings
        }


def get_stats_with_author(
    plugins: List[Dict],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, Any]:
    """Get download statistics with author information.

    Args:
        plugins: List of plugin info from scan_plugins()
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        Statistics with author info added
    """
    # Build skill to author mapping from plugins
    skill_author_map = {}
    for plugin in plugins:
        skill_name = plugin.get("name", "")
        metadata = plugin.get("metadata", {})

        # Author can be in multiple locations:
        # 1. metadata.author (top-level in YAML frontmatter)
        # 2. metadata.metadata.author (inside metadata section in YAML frontmatter)
        author = metadata.get("author") or metadata.get("metadata", {}).get("author")

        # Handle different author formats
        if isinstance(author, dict):
            author_name = author.get("name", "Unknown")
        elif isinstance(author, str) and author:
            author_name = author
        else:
            author_name = "Unknown"

        # Map both base name and versioned names (from versions array)
        skill_author_map[skill_name] = author_name
        for version_info in plugin.get("versions", []):
            filename = version_info.get("filename", "")
            # Remove .zip extension to match skill_name in downloads table
            if filename.endswith(".zip"):
                versioned_name = filename[:-4]
                skill_author_map[versioned_name] = author_name

    # Get download stats
    stats = get_download_stats(start_date, end_date)

    # Filter rankings to only include skills that still exist (active)
    # This prevents deleted/inactive skills from appearing in hot rankings
    filtered_rankings = []
    valid_skill_names = set(skill_author_map.keys())
    for ranking in stats["rankings"]:
        # Only include skills that are still in the plugins list (active)
        if ranking["skill_name"] in valid_skill_names:
            ranking["author"] = skill_author_map.get(ranking["skill_name"], "Unknown")
            filtered_rankings.append(ranking)

    stats["rankings"] = filtered_rankings
    return stats


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


def check_skill_exists(skill_name: str) -> bool:
    """Check if a skill with the given name already exists.

    Args:
        skill_name: The name of the skill

    Returns:
        True if skill exists, False otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as count FROM skills
            WHERE skill_name = %s
            """,
            (skill_name,)
        ).fetchone()

        return row["count"] > 0 if row else False


def get_skill_by_name(skill_name: str) -> Optional[Dict[str, Any]]:
    """Get a skill by its name.

    Args:
        skill_name: The name of the skill

    Returns:
        Dictionary with skill record or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id, skill_name, version, filename, uploader_id, status,
                source_type, uploaded_at, reviewed_at, reviewer_id,
                review_comment, is_active, description, metadata
            FROM skills
            WHERE skill_name = %s
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "source_type": row["source_type"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"],
                "is_active": row["is_active"],
                "description": row["description"],
                "metadata": row["metadata"]
            }
        return None


def create_skill_record(
    skill_name: str,
    version: str,
    filename: str,
    uploader_id: int,
    status: str,
    source_type: str = 'opensource'
) -> int:
    """Create a skill record.

    Args:
        skill_name: The name of the skill
        version: The version of the skill
        filename: The filename of the skill
        uploader_id: The ID of the user uploading the skill
        status: The status of the skill
        source_type: The source type of the skill (opensource, icsl, huawei)

    Returns:
        The ID of the inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status, source_type, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (skill_name, version, filename, uploader_id, status, source_type)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_skills() -> List[Dict[str, Any]]:
    """Get all pending skills with uploader information.

    Returns:
        List of pending skill dictionaries with uploader info
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.skill_name,
                s.version,
                s.filename,
                s.uploader_id,
                s.status,
                s.source_type,
                s.uploaded_at,
                s.reviewed_at,
                s.reviewer_id,
                s.review_comment,
                u.employee_id as uploader_employee_id
            FROM skills s
            JOIN users u ON s.uploader_id = u.id
            WHERE s.status = 'pending'
            """
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "source_type": row["source_type"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"],
                "uploader_employee_id": row["uploader_employee_id"]
            })

        return results


def get_skill_by_id(skill_id: int) -> Optional[Dict[str, Any]]:
    """Get a skill by its ID.

    Args:
        skill_id: The skill's ID

    Returns:
        Skill dictionary if found, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                uploader_id,
                status,
                source_type,
                uploaded_at,
                reviewed_at,
                reviewer_id,
                review_comment
            FROM skills
            WHERE id = %s
            """,
            (skill_id,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "source_type": row["source_type"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"]
            }
        return None


def update_skill_status(
    skill_id: int,
    status: str,
    reviewer_id: Optional[int] = None,
    comment: Optional[str] = None
) -> None:
    """Update the status of a skill.

    Args:
        skill_id: The skill's ID
        status: The new status (e.g., 'approved', 'rejected')
        reviewer_id: The ID of the reviewer (optional)
        comment: Review comment (optional)
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE skills
            SET status = %s,
                reviewed_at = CURRENT_TIMESTAMP,
                reviewer_id = %s,
                review_comment = %s
            WHERE id = %s
            """,
            (status, reviewer_id, comment, skill_id)
        )
        conn.commit()


def get_user_uploads(user_id: int) -> List[Dict[str, Any]]:
    """Get all uploads by a specific user.

    Args:
        user_id: The user's ID

    Returns:
        List of skill dictionaries uploaded by the user
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                uploader_id,
                status,
                source_type,
                uploaded_at,
                reviewed_at,
                reviewer_id,
                review_comment
            FROM skills
            WHERE uploader_id = %s
            """,
            (user_id,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "source_type": row["source_type"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"]
            })

        return results


def get_user_downloads(
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Get download history for a specific user.

    Args:
        user_id: The user's ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        limit: Maximum number of records to return
        offset: Number of records to skip for pagination

    Returns:
        Dictionary containing:
        - downloads: List of download records
        - total: Total count matching the filter
        - limit: The limit used
        - offset: The offset used
    """
    # Default to all time if no dates provided
    if start_date is None:
        start_date = date(1970, 1, 1)
    if end_date is None:
        end_date = date.today()

    with get_connection() as conn:
        # Get total count
        total_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE user_id = %s
              AND DATE(downloaded_at) BETWEEN %s AND %s
            """,
            (user_id, start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total = total_row["total"] if total_row else 0

        # Get paginated results
        rows = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                downloaded_at,
                ip_address,
                user_agent
            FROM downloads
            WHERE user_id = %s
              AND DATE(downloaded_at) BETWEEN %s AND %s
            ORDER BY downloaded_at DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, start_date.isoformat(), end_date.isoformat(), limit, offset)
        ).fetchall()

        downloads = []
        for row in rows:
            downloads.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "downloaded_at": row["downloaded_at"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"]
            })

        return {
            "downloads": downloads,
            "total": total,
            "limit": limit,
            "offset": offset
        }


def get_total_users_count() -> int:
    """Get total count of users in the system.

    Returns:
        Total number of users
    """
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        return row["count"] if row else 0


def get_skills_count_by_status(status: str) -> int:
    """Get count of skills by status.

    Args:
        status: The status to filter by ('pending', 'approved', 'rejected')

    Returns:
        Count of skills with the given status
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM skills WHERE status = %s",
            (status,)
        ).fetchone()
        return row["count"] if row else 0


def get_today_downloads_count() -> int:
    """Get count of downloads today.

    Returns:
        Number of downloads today
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as count FROM downloads
            WHERE DATE(downloaded_at) = CURDATE()
            """
        ).fetchone()
        return row["count"] if row else 0


def get_top_skills_by_downloads(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top skills by download count.

    Args:
        limit: Maximum number of skills to return

    Returns:
        List of skills with download counts
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as download_count
            FROM downloads
            GROUP BY skill_name
            ORDER BY download_count DESC
            LIMIT %s
            """,
            (limit,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "skill_name": row["skill_name"],
                "downloads": row["download_count"]
            })

        return results


def get_top_users_by_downloads(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by download count.

    Args:
        limit: Maximum number of users to return

    Returns:
        List of users with download counts
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.employee_id,
                u.role,
                COUNT(d.id) as download_count
            FROM users u
            LEFT JOIN downloads d ON u.id = d.user_id
            GROUP BY u.id
            ORDER BY download_count DESC
            LIMIT %s
            """,
            (limit,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "employee_id": row["employee_id"],
                "role": row["role"],
                "downloads": row["download_count"]
            })

        return results


def get_upload_stats() -> Dict[str, Any]:
    """Get upload statistics for dashboard.

    Returns:
        Dict containing:
        - total_skills: Total number of uploaded skills
        - this_month: Number of skills uploaded this month
        - last_month: Number of skills uploaded last month
        - top_uploaders: List of top 10 uploaders with username and count
    """
    with get_connection() as conn:
        # Total skills count
        total_row = conn.execute(
            "SELECT COUNT(*) as count FROM skills"
        ).fetchone()
        total_skills = total_row["count"] if total_row else 0

        # This month's uploads
        this_month_row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM skills
            WHERE YEAR(uploaded_at) = YEAR(CURDATE())
            AND MONTH(uploaded_at) = MONTH(CURDATE())
            """
        ).fetchone()
        this_month = this_month_row["count"] if this_month_row else 0

        # Last month's uploads
        last_month_row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM skills
            WHERE YEAR(uploaded_at) = YEAR(CURDATE() - INTERVAL 1 MONTH)
            AND MONTH(uploaded_at) = MONTH(CURDATE() - INTERVAL 1 MONTH)
            """
        ).fetchone()
        last_month = last_month_row["count"] if last_month_row else 0

        # Top 10 uploaders
        top_uploaders_rows = conn.execute(
            """
            SELECT u.employee_id, u.name, u.minDepartment, u.team, u.`group`, COUNT(s.id) as upload_count
            FROM users u
            INNER JOIN skills s ON u.id = s.uploader_id
            GROUP BY u.id, u.employee_id, u.name, u.minDepartment, u.team, u.`group`
            ORDER BY upload_count DESC
            LIMIT 10
            """
        ).fetchall()

        top_uploaders = []
        for row in top_uploaders_rows:
            top_uploaders.append({
                "username": row["employee_id"],
                "name": row["name"] or row["employee_id"],
                "minDepartment": row["minDepartment"],
                "team": row["team"],
                "group": row["group"],
                "upload_count": row["upload_count"]
            })

        return {
            "total_skills": total_skills,
            "this_month": this_month,
            "last_month": last_month,
            "top_uploaders": top_uploaders
        }


def get_skill_source_type(skill_name: str) -> Optional[str]:
    """Get the source type for a skill by name.

    Args:
        skill_name: The name of the skill

    Returns:
        Source type string (opensource, icsl, huawei) or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT source_type
            FROM skills
            WHERE skill_name = %s
            ORDER BY uploaded_at DESC
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        return row["source_type"] if row else None


def create_user(employee_id: str, api_key: str, role: str = "user") -> int:
    """Create a new user in the system.

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
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (employee_id, api_key, role, 1, 0)  # status=1 means active, skills_count=0
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
        - total: Total count matching the filter
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

        # Get paginated results with dynamic skills count using LEFT JOIN
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""
            SELECT u.id, u.employee_id, u.role, u.status,
                   COALESCE(COUNT(s.id), 0) as skills_count,
                   u.created_at, u.last_login
            FROM users u
            LEFT JOIN skills s ON s.uploader_id = u.id
            {where_clause}
            GROUP BY u.id
            ORDER BY u.created_at DESC
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


def get_user_skills_count(user_id: int) -> int:
    """Get the number of active skills for a user.

    Args:
        user_id: The user's ID

    Returns:
        Count of active skills
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM skills
            WHERE uploader_id = %s AND is_active = 1
            """,
            (user_id,)
        ).fetchone()
        return row["count"] if row else 0


def migrate_add_user_management_features():
    """Migrate database to add user management and notification features.

    Adds columns:
    - users.status (default 'active')
    - users.skills_count (default 0)
    - skills.is_active (default 1)
    - skills.is_default_version (default 0)

    Creates notifications table with indexes.
    """
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


def migrate_add_skill_description_and_metadata():
    """Migrate database to add description and metadata columns to skills table.

    Adds columns:
    - skills.description (TEXT, nullable)
    - skills.metadata (TEXT, nullable, JSON format)

    These columns are needed for the external API to provide skill details.
    """
    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # Check existing columns
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        # Add description column to skills table
        if "description" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN description TEXT")
            conn.commit()
            logger.info("Migration: Added description column to skills table")

        # Add metadata column to skills table
        if "metadata" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN metadata TEXT")
            conn.commit()
            logger.info("Migration: Added metadata column to skills table")

        # Add created_at column if not exists (for ordering)
        # Note: Cannot use DEFAULT CURRENT_TIMESTAMP as uploaded_at already uses it
        if "created_at" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN created_at TIMESTAMP NULL")
            conn.commit()
            logger.info("Migration: Added created_at column to skills table")

        logger.info("Migration: skill_description_and_metadata migration completed")


def migrate_to_single_version():
    """Migrate database to single version model for skills.

    Changes:
    1. Clean up duplicate skill_name records (keep default version or earliest)
    2. Add UNIQUE KEY idx_skill_name (skill_name)
    3. Drop is_default_version column

    This migration implements the single-version model where each skill_name
    is unique and owned by a single user.
    """
    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # Step 1: Check if unique index already exists
        cursor.execute("""
            SELECT COUNT(*) as count FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND table_name = 'skills' AND index_name = 'idx_skill_name'
        """)
        if cursor.fetchone()["count"] > 0:
            logger.info("Migration: idx_skill_name already exists, skipping migration")
            return

        # Step 2: Clean up duplicate skill_name records
        # Keep the record with is_default_version=1, or the earliest uploaded_at
        # First, delete notifications that reference the duplicate skills
        cursor.execute("""
            DELETE n FROM notifications n
            INNER JOIN skills s1 ON n.related_skill_id = s1.id
            INNER JOIN skills s2 ON s1.skill_name = s2.skill_name
            WHERE s1.id > s2.id
        """)
        conn.commit()

        # Then delete the duplicate skill records
        cursor.execute("""
            DELETE t1 FROM skills t1
            INNER JOIN skills t2
            WHERE t1.skill_name = t2.skill_name
              AND t1.id > t2.id
        """)
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(f"Migration: Deleted {deleted_count} duplicate skill records")

        # Step 3: Add unique index on skill_name (use prefix index due to 767 byte limit)
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skill_name",
            "CREATE UNIQUE INDEX idx_skill_name ON skills(skill_name(191))"
        )
        logger.info("Migration: Added unique index idx_skill_name on skills table")

        # Step 4: Drop is_default_version column
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]
        if "is_default_version" in columns:
            conn.execute("ALTER TABLE skills DROP COLUMN is_default_version")
            conn.commit()
            logger.info("Migration: Dropped is_default_version column from skills table")

        logger.info("Migration: to_single_version migration completed")


def create_notification(
    user_id: int,
    type: str,
    title: str,
    content: Optional[str] = None,
    related_skill_id: Optional[int] = None
) -> int:
    """Create a notification for a user.

    Args:
        user_id: The user's ID
        type: Notification type (e.g., 'review_success', 'review_rejected')
        title: Notification title
        content: Optional notification content
        related_skill_id: Optional related skill ID

    Returns:
        The ID of the created notification
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, content, related_skill_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, type, title, content, related_skill_id)
        )
        conn.commit()
        return cursor.lastrowid


def get_user_notifications(
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Get notifications for a user.

    Args:
        user_id: The user's ID
        unread_only: If True, only return unread notifications
        limit: Maximum number of notifications to return
        offset: Number of notifications to skip for pagination

    Returns:
        Dictionary containing:
        - notifications: List of notification records
        - total: Total count matching the filter
        - unread_count: Count of unread notifications
    """
    with get_connection() as conn:
        # Get total count
        if unread_only:
            total_row = conn.execute(
                "SELECT COUNT(*) as total FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,)
            ).fetchone()
        else:
            total_row = conn.execute(
                "SELECT COUNT(*) as total FROM notifications WHERE user_id = %s",
                (user_id,)
            ).fetchone()

        total = total_row["total"] if total_row else 0

        # Get unread count
        unread_row = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (user_id,)
        ).fetchone()
        unread_count = unread_row["count"] if unread_row else 0

        # Build query
        if unread_only:
            query = """
                SELECT id, user_id, type, title, content, related_skill_id, is_read, created_at
                FROM notifications
                WHERE user_id = %s AND is_read = 0
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            rows = conn.execute(query, (user_id, limit, offset)).fetchall()
        else:
            query = """
                SELECT id, user_id, type, title, content, related_skill_id, is_read, created_at
                FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            rows = conn.execute(query, (user_id, limit, offset)).fetchall()

        notifications = []
        for row in rows:
            notifications.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "type": row["type"],
                "title": row["title"],
                "content": row["content"],
                "related_skill_id": row["related_skill_id"],
                "is_read": row["is_read"],
                "created_at": row["created_at"]
            })

        return {
            "notifications": notifications,
            "total": total,
            "unread_count": unread_count
        }


def mark_notification_read(notification_id: int, user_id: int) -> bool:
    """Mark a notification as read.

    Args:
        notification_id: The notification's ID
        user_id: The user's ID (for ownership verification)

    Returns:
        True if marked as read, False if notification not found or not owned by user
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE notifications
            SET is_read = 1
            WHERE id = %s AND user_id = %s
            """,
            (notification_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    """Mark all notifications as read for a user.

    Args:
        user_id: The user's ID

    Returns:
        Number of notifications marked as read
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE notifications
            SET is_read = 1
            WHERE user_id = %s AND is_read = 0
            """,
            (user_id,)
        )
        conn.commit()
        return cursor.rowcount


def get_unread_notifications_count(user_id: int) -> int:
    """Get count of unread notifications for a user.

    Args:
        user_id: The user's ID

    Returns:
        Count of unread notifications
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (user_id,)
        ).fetchone()
        return row["count"] if row else 0


def cleanup_old_notifications(user_id: int, keep_count: int = 100) -> None:
    """Delete old notifications keeping only the most recent ones.

    Args:
        user_id: The user's ID
        keep_count: Number of recent notifications to keep
    """
    with get_connection() as conn:
        # Find the cutoff point
        rows = conn.execute(
            """
            SELECT id FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, 1, keep_count)
        ).fetchall()

        if rows:
            # Delete all notifications older than the cutoff
            cutoff_id = rows[0]["id"]
            conn.execute(
                "DELETE FROM notifications WHERE user_id = %s AND id < %s",
                (user_id, cutoff_id)
            )
            conn.commit()


def update_skill_active_status(skill_id: int, is_active: bool) -> bool:
    """Update the active status of a skill.

    Args:
        skill_id: The skill's ID
        is_active: Whether the skill should be active

    Returns:
        True if updated, False if skill not found
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE skills
            SET is_active = %s
            WHERE id = %s
            """,
            (1 if is_active else 0, skill_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def set_skill_default_version(skill_id: int, skill_name: str) -> bool:
    """Set a skill version as the default version.

    This will:
    1. Set is_default_version = 0 for all versions of the same skill_name
    2. Set is_default_version = 1 for the specified skill_id

    Args:
        skill_id: The skill version ID to set as default
        skill_name: The skill name (to clear other versions' default status)

    Returns:
        True if updated successfully, False otherwise
    """
    with get_connection() as conn:
        # First, clear default status for all versions of this skill
        conn.execute(
            """
            UPDATE skills
            SET is_default_version = 0
            WHERE skill_name = %s
            """,
            (skill_name,)
        )

        # Then, set the specified version as default
        cursor = conn.execute(
            """
            UPDATE skills
            SET is_default_version = 1
            WHERE id = %s
            """,
            (skill_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_skill_active_status(skill_name: str) -> bool:
    """Get the active status for a skill by name.

    Args:
        skill_name: The name of the skill

    Returns:
        True if skill is active (is_active = 1), False if inactive or not found
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT is_active
            FROM skills
            WHERE skill_name = %s
            ORDER BY uploaded_at DESC
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        return bool(row["is_active"]) if row else True


def get_skill_approval_status(skill_name: str) -> bool:
    """Check if a skill has been approved (status = 'approved').

    Args:
        skill_name: The name of the skill

    Returns:
        True if the skill has been approved, False otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT status
            FROM skills
            WHERE skill_name = %s
            ORDER BY uploaded_at DESC
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        return row["status"] == "approved" if row else False


def get_my_skills(
    user_id: int,
    status_filter: str = "all",
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """Get skills uploaded by a specific user with filtering and pagination.

    Args:
        user_id: The user's ID
        status_filter: Filter by status ('all', 'active', 'unlisted', 'pending', 'rejected')
        limit: Maximum number of records to return
        offset: Number of records to skip for pagination

    Returns:
        Dictionary containing:
        - skills: List of skill records
        - total: Total count matching the filter
        - limit: The limit used
        - offset: The offset used
    """
    with get_connection() as conn:
        # Build base query
        base_query = "FROM skills WHERE uploader_id = %s"
        params = [user_id]

        # Add status filter
        if status_filter == "active":
            base_query += " AND status = 'approved' AND is_active = 1"
        elif status_filter == "unlisted":
            base_query += " AND status = 'approved' AND is_active = 0"
        elif status_filter == "pending":
            base_query += " AND status = 'pending'"
        elif status_filter == "rejected":
            base_query += " AND status = 'rejected'"
        # 'all' returns all skills regardless of status

        # Get total count
        total_row = conn.execute(
            f"SELECT COUNT(*) as total {base_query}",
            tuple(params)
        ).fetchone()
        total = total_row["total"] if total_row else 0

        # Get paginated results
        rows = conn.execute(
            f"""
            SELECT
                id, skill_name, version, filename, uploader_id, status,
                source_type, uploaded_at, reviewed_at, reviewer_id,
                review_comment, is_active
            {base_query}
            ORDER BY uploaded_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, offset])
        ).fetchall()

        skills = []
        for row in rows:
            skills.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "source_type": row["source_type"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"],
                "is_active": row["is_active"]
            })

        return {
            "skills": skills,
            "total": total,
            "limit": limit,
            "offset": offset
        }


def delete_skill_version(user_id: int, skill_id: int, is_admin: bool = False) -> bool:
    """Delete a skill.

    Only the owner of the skill can delete it, unless user is admin.
    The physical ZIP file will also be removed from the plugins directory.

    Args:
        user_id: The user's ID (for ownership verification, ignored if is_admin=True)
        skill_id: The ID of the skill to delete
        is_admin: If True, skip ownership check (admin can delete any skill)

    Returns:
        True if deleted successfully, False if skill not found or not owned by user
    """
    import os
    from pathlib import Path

    with get_connection() as conn:
        # Admin users can delete any skill - get skill info without ownership check
        # Non-admin users must own the skill
        if is_admin:
            verify_row = conn.execute(
                """
                SELECT id, filename, skill_name, uploader_id
                FROM skills
                WHERE id = %s
                """,
                (skill_id,)
            ).fetchone()
        else:
            verify_row = conn.execute(
                """
                SELECT id, filename, skill_name
                FROM skills
                WHERE id = %s AND uploader_id = %s
                """,
                (skill_id, user_id)
            ).fetchone()

        if not verify_row:
            return False

        filename = verify_row["filename"]
        skill_name = verify_row["skill_name"]
        uploader_id = verify_row.get("uploader_id", user_id)

        # Delete related notifications first (due to foreign key constraint)
        conn.execute(
            """
            DELETE FROM notifications
            WHERE related_skill_id = %s
            """,
            (skill_id,)
        )

        # Delete related Gitea push tasks (due to foreign key constraint)
        conn.execute(
            """
            DELETE FROM gitea_push_tasks
            WHERE skill_id = %s
            """,
            (skill_id,)
        )

        # Delete the skill record
        # For admin, delete by id only (no ownership check needed)
        # For non-admin, check uploader_id to ensure ownership
        if is_admin:
            cursor = conn.execute(
                """
                    DELETE FROM skills
                    WHERE id = %s
                    """,
                (skill_id,)
            )
        else:
            cursor = conn.execute(
                """
                    DELETE FROM skills
                    WHERE id = %s AND uploader_id = %s
                    """,
                (skill_id, user_id)
            )

        conn.commit()

        # Delete related download records
        # The downloads table stores skill_name with version (e.g., 'api-processing-798-3.1.0')
        # So we need to delete by filename pattern to catch all download records
        # Use LIKE to match any downloads with this filename as base
        conn.execute(
            """
            DELETE FROM downloads
            WHERE filename LIKE %s
            """,
            (f"{filename}%",)
        )

        # Delete the physical ZIP file
        if filename:
            zip_path = Path("./plugins") / filename
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception as e:
                    # Log but don't fail the database operation
                    logger.warning(f"Could not delete file {zip_path}: {e}", extra={"zip_path": str(zip_path)})

        return cursor.rowcount > 0


def batch_unlist_skills(user_id: int, skill_ids: List[int]) -> Dict[str, Any]:
    """Unlist multiple skills at once.

    Args:
        user_id: The user's ID
        skill_ids: List of skill IDs to unlist

    Returns:
        Dictionary with success count and failed IDs
    """
    with get_connection() as conn:
        success_count = 0
        failed_ids = []

        for skill_id in skill_ids:
            # Verify ownership
            verify_row = conn.execute(
                """
                SELECT id FROM skills
                WHERE id = %s AND uploader_id = %s
                """,
                (skill_id, user_id)
            ).fetchone()

            if verify_row:
                conn.execute(
                    """
                    UPDATE skills
                    SET is_active = 0
                    WHERE id = %s
                    """,
                    (skill_id,)
                )
                success_count += 1
            else:
                failed_ids.append(skill_id)

        conn.commit()

        return {
            "success_count": success_count,
            "failed_ids": failed_ids
        }


def batch_delete_skills(user_id: int, skill_ids: List[int]) -> Dict[str, Any]:
    """Delete multiple skills at once.

    Args:
        user_id: The user's ID
        skill_ids: List of skill IDs to delete

    Returns:
        Dictionary with success count and failed IDs
    """
    import os
    from pathlib import Path

    with get_connection() as conn:
        success_count = 0
        failed_ids = []
        files_to_delete = []

        for skill_id in skill_ids:
            # Admin can delete any skill, no ownership check needed
            verify_row = conn.execute(
                """
                SELECT id, filename, skill_name, uploader_id
                FROM skills
                WHERE id = %s
                """,
                (skill_id,)
            ).fetchone()

            if verify_row:
                filename = verify_row["filename"]
                skill_name = verify_row["skill_name"]

                # Delete related notifications first (due to foreign key constraint)
                conn.execute(
                    """
                    DELETE FROM notifications
                    WHERE related_skill_id = %s
                    """,
                    (skill_id,)
                )

                # Delete the skill record
                conn.execute(
                    """
                    DELETE FROM skills
                    WHERE id = %s
                    """,
                    (skill_id,)
                )

                # Track file for deletion
                if filename:
                    files_to_delete.append(filename)

                success_count += 1
            else:
                failed_ids.append(skill_id)

        conn.commit()

        # Delete physical ZIP files
        plugins_dir = Path("./plugins")
        for filename in files_to_delete:
            zip_path = plugins_dir / filename
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete file {zip_path}: {e}", extra={"zip_path": str(zip_path)})

        return {
            "success_count": success_count,
            "failed_ids": failed_ids
        }


def init_external_api_tables():
    """初始化外部 API 相关的数据库表"""
    with get_connection() as conn:
        # 创建 external_api_keys 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS external_api_keys (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NULL,
                api_key VARCHAR(64) UNIQUE NOT NULL,
                name VARCHAR(100),
                is_active TINYINT(1) DEFAULT 1,
                rate_limit INT DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP NULL,
                INDEX idx_api_key (api_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 创建 api_call_logs 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_call_logs (
                id INT PRIMARY KEY AUTO_INCREMENT,
                api_key_id INT NOT NULL,
                endpoint VARCHAR(255) NOT NULL,
                method VARCHAR(10) NOT NULL,
                params TEXT,
                ip_address VARCHAR(45),
                status_code INT,
                response_time_ms INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_key_id) REFERENCES external_api_keys(id),
                INDEX idx_api_key_time (api_key_id, created_at),
                INDEX idx_endpoint (endpoint)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 迁移：修改 user_id 为可空（如果表已存在且为 NOT NULL）
        migrate_api_keys_user_id_nullable(conn)

        conn.commit()


def create_api_key(user_id: int, name: str = None, rate_limit: int = 100) -> Optional[Dict[str, Any]]:
    """创建新的 API Key"""
    api_key = f"sk_{secrets.token_urlsafe(32)}"

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO external_api_keys (user_id, api_key, name, rate_limit)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, api_key, name, rate_limit)
            )
            conn.commit()

            return {
                'id': cursor.lastrowid,
                'api_key': api_key,
                'user_id': user_id,
                'name': name,
                'rate_limit': rate_limit,
                'is_active': 1
            }
    except Exception as e:
        logger.error(f"创建 API Key 失败: {e}")
        return None


def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """验证 API Key 并返回信息"""
    with get_connection() as conn:
        result = conn.execute(
            """
            SELECT id, user_id, api_key, name, is_active, rate_limit
            FROM external_api_keys
            WHERE api_key = %s AND is_active = 1
            """,
            (api_key,)
        ).fetchone()

        if result:
            # 更新最后使用时间
            conn.execute(
                "UPDATE external_api_keys SET last_used_at = NOW() WHERE id = %s",
                (result['id'],)
            )
            conn.commit()
            return dict(result)

        return None


def get_api_key_info(api_key: str) -> Optional[Dict[str, Any]]:
    """获取 API Key 详细信息"""
    with get_connection() as conn:
        result = conn.execute(
            """
            SELECT * FROM external_api_keys WHERE api_key = %s
            """,
            (api_key,)
        ).fetchone()

        return dict(result) if result else None


def deactivate_api_key(api_key_id: int) -> bool:
    """停用 API Key"""
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE external_api_keys SET is_active = 0 WHERE id = %s",
                (api_key_id,)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"停用 API Key 失败: {e}")
        return False


def log_api_call(api_key_id: int, endpoint: str, method: str,
                 params: str = None, ip_address: str = None,
                 status_code: int = None, response_time_ms: int = None):
    """记录 API 调用日志"""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_call_logs
                (api_key_id, endpoint, method, params, ip_address, status_code, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (api_key_id, endpoint, method, params, ip_address, status_code, response_time_ms)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"记录 API 调用日志失败: {e}")


def get_api_keys_list(page: int = 1, per_page: int = 20, search: str = None,
                       status_filter: str = None) -> Dict[str, Any]:
    """获取 API Keys 列表（分页、搜索、过滤）"""
    try:
        with get_connection() as conn:
            # 构建 WHERE 条件
            conditions = []
            params = []

            if search:
                conditions.append("(eak.name LIKE %s OR COALESCE(u.employee_id, '管理员') LIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])

            if status_filter == "active":
                conditions.append("eak.is_active = 1")
            elif status_filter == "inactive":
                conditions.append("eak.is_active = 0")

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # 获取总数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM external_api_keys eak
                LEFT JOIN users u ON eak.user_id = u.id
                {where_clause}
            """
            total_result = conn.execute(count_query, params).fetchone()
            total = total_result['total'] if total_result else 0

            # 获取数据
            offset = (page - 1) * per_page
            data_query = f"""
                SELECT eak.*, COALESCE(u.employee_id, '管理员') as employee_id
                FROM external_api_keys eak
                LEFT JOIN users u ON eak.user_id = u.id
                {where_clause}
                ORDER BY eak.created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            items = conn.execute(data_query, params).fetchall()

            return {
                "items": [dict(item) for item in items],
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }
    except Exception as e:
        logger.error(f"获取 API Keys 列表失败: {e}")
        return {
            "items": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0
        }


def delete_api_key(api_key_id: int) -> bool:
    """删除 API Key"""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM external_api_keys WHERE id = %s", (api_key_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"删除 API Key 失败: {e}")
        return False


def toggle_api_key_status(api_key_id: int) -> Optional[Dict[str, Any]]:
    """切换 API Key 状态（启用/禁用）"""
    try:
        with get_connection() as conn:
            # 获取当前状态
            result = conn.execute(
                "SELECT is_active FROM external_api_keys WHERE id = %s",
                (api_key_id,)
            ).fetchone()

            if not result:
                return None

            new_status = 0 if result['is_active'] == 1 else 1

            conn.execute(
                "UPDATE external_api_keys SET is_active = %s WHERE id = %s",
                (new_status, api_key_id)
            )
            conn.commit()

            return {"id": api_key_id, "is_active": new_status}
    except Exception as e:
        logger.error(f"切换 API Key 状态失败: {e}")
        return None


def get_api_key_stats(api_key_id: int) -> Optional[Dict[str, Any]]:
    """获取 API Key 调用统计"""
    try:
        with get_connection() as conn:
            # 总调用次数
            total_calls = conn.execute(
                "SELECT COUNT(*) as count FROM api_call_logs WHERE api_key_id = %s",
                (api_key_id,)
            ).fetchone()

            # 成功调用次数（状态码 2xx）
            success_calls = conn.execute(
                "SELECT COUNT(*) as count FROM api_call_logs WHERE api_key_id = %s AND status_code >= 200 AND status_code < 300",
                (api_key_id,)
            ).fetchone()

            # 最后调用时间
            last_call = conn.execute(
                "SELECT MAX(created_at) as last_call FROM api_call_logs WHERE api_key_id = %s",
                (api_key_id,)
            ).fetchone()

            # 今日调用次数
            today_calls = conn.execute(
                "SELECT COUNT(*) as count FROM api_call_logs WHERE api_key_id = %s AND DATE(created_at) = CURDATE()",
                (api_key_id,)
            ).fetchone()

            # 最近7天调用趋势
            trend = conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM api_call_logs
                WHERE api_key_id = %s AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY date
            """, (api_key_id,)).fetchall()

            return {
                "total_calls": total_calls['count'] if total_calls else 0,
                "success_calls": success_calls['count'] if success_calls else 0,
                "last_call": last_call['last_call'].isoformat() if last_call and last_call['last_call'] else None,
                "today_calls": today_calls['count'] if today_calls else 0,
                "trend": [{"date": str(row['date']), "count": row['count']} for row in trend]
            }
    except Exception as e:
        logger.error(f"获取 API Key 统计失败: {e}")
        return None


def migrate_api_keys_user_id_nullable(conn):
    """迁移：将 external_api_keys 表的 user_id 改为可空"""
    try:
        # 检查外键约束是否存在
        fk_check = conn.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'external_api_keys'
            AND CONSTRAINT_NAME = 'external_api_keys_ibfk_1'
        """).fetchone()

        if fk_check:
            logger.info("Migration: Dropping foreign key constraint on external_api_keys.user_id")
            conn.execute("ALTER TABLE external_api_keys DROP FOREIGN KEY external_api_keys_ibfk_1")

        # 检查 user_id 是否为 NOT NULL
        column_info = conn.execute("""
            SELECT IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'external_api_keys'
            AND COLUMN_NAME = 'user_id'
        """).fetchone()

        if column_info and column_info['IS_NULLABLE'] == 'NO':
            logger.info("Migration: Making external_api_keys.user_id nullable")
            # 先将现有记录的 user_id 设为一个有效值或 NULL
            conn.execute("UPDATE external_api_keys SET user_id = NULL WHERE user_id NOT IN (SELECT id FROM users)")
            # 修改列为可空
            conn.execute("ALTER TABLE external_api_keys MODIFY user_id INT NULL")

        logger.info("Migration: external_api_keys.user_id is now nullable")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        # 不抛出异常，允许继续执行


# ============================================
# 评分评论系统
# ============================================

def migrate_add_rating_comment_system():
    """迁移：添加评分评论系统表和 skills 表相关字段"""
    with get_connection() as conn:
        cursor = conn._conn.cursor()

        # 检查表是否存在
        cursor.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'skill_ratings'
        """)
        ratings_table_exists = cursor.fetchone()["count"] > 0

        cursor.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = 'skill_comments'
        """)
        comments_table_exists = cursor.fetchone()["count"] > 0

        # 创建 skill_ratings 表（如果不存在）
        if not ratings_table_exists:
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS skill_ratings (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        skill_id INT NOT NULL,
                        user_id INT NOT NULL,
                        rating TINYINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        UNIQUE KEY uk_skill_user (skill_id, user_id),
                        INDEX idx_skill_rating (skill_id, rating)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                conn.commit()
            except Exception as e:
                if "1293" in str(e):  # 表定义错误，说明表已存在但定义有问题，跳过
                    logger.warning("Migration: skill_ratings table exists with definition issue, skipping")
                else:
                    raise

        # 创建 skill_comments 表（如果不存在）
        if not comments_table_exists:
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS skill_comments (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        skill_id INT NOT NULL,
                        user_id INT NOT NULL,
                        content VARCHAR(500) NOT NULL,
                        rating_id INT DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
                        is_deleted TINYINT(1) DEFAULT 0,
                        FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (rating_id) REFERENCES skill_ratings(id) ON DELETE SET NULL,
                        INDEX idx_skill_created (skill_id, created_at DESC),
                        INDEX idx_user_comments (user_id, created_at DESC)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)
                conn.commit()
            except Exception as e:
                if "1293" in str(e):  # 表定义错误，说明表已存在但定义有问题，跳过
                    logger.warning("Migration: skill_comments table exists with definition issue, skipping")
                else:
                    raise

        # 给 skills 表添加评分统计字段
        cursor = conn._conn.cursor()
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "rating_average" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN rating_average DECIMAL(2,1) DEFAULT 0.0")
            logger.info("Migration: Added rating_average column to skills table")

        if "rating_count" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN rating_count INT DEFAULT 0")
            logger.info("Migration: Added rating_count column to skills table")

        if "comment_count" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN comment_count INT DEFAULT 0")
            logger.info("Migration: Added comment_count column to skills table")

        conn.commit()
        logger.info("Migration: rating_comment_system migration completed")


def submit_rating(skill_id: int, user_id: int, rating: int) -> Dict[str, Any]:
    """提交或更新评分

    Args:
        skill_id: 技能ID
        user_id: 用户ID
        rating: 评分 (1-5)

    Returns:
        操作结果
    """
    if rating < 1 or rating > 5:
        return {"success": False, "error": "评分必须在 1-5 之间"}

    with get_connection() as conn:
        # 检查是否已评分
        existing = conn.execute(
            "SELECT id FROM skill_ratings WHERE skill_id = %s AND user_id = %s",
            (skill_id, user_id)
        ).fetchone()

        if existing:
            # 更新评分
            conn.execute(
                "UPDATE skill_ratings SET rating = %s WHERE skill_id = %s AND user_id = %s",
                (rating, skill_id, user_id)
            )
        else:
            # 新增评分
            conn.execute(
                "INSERT INTO skill_ratings (skill_id, user_id, rating) VALUES (%s, %s, %s)",
                (skill_id, user_id, rating)
            )

        # 更新技能的评分统计
        _update_skill_rating_stats(conn, skill_id)
        conn.commit()

        return {"success": True, "rating": rating}


def get_user_rating(skill_id: int, user_id: int) -> Optional[int]:
    """获取用户对技能的评分

    Args:
        skill_id: 技能ID
        user_id: 用户ID

    Returns:
        评分值或 None
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT rating FROM skill_ratings WHERE skill_id = %s AND user_id = %s",
            (skill_id, user_id)
        ).fetchone()
        return row["rating"] if row else None


def get_skill_ratings(skill_id: int) -> Dict[str, Any]:
    """获取技能的评分统计

    Args:
        skill_id: 技能ID

    Returns:
        评分统计信息
    """
    with get_connection() as conn:
        # 获取评分分布
        distribution = conn.execute(
            """
            SELECT rating, COUNT(*) as count
            FROM skill_ratings
            WHERE skill_id = %s
            GROUP BY rating
            ORDER BY rating
            """,
            (skill_id,)
        ).fetchall()

        # 获取平均分和总数
        stats = conn.execute(
            """
            SELECT
                COALESCE(AVG(rating), 0) as average,
                COUNT(*) as total
            FROM skill_ratings
            WHERE skill_id = %s
            """,
            (skill_id,)
        ).fetchone()

        distribution_dict = {i: 0 for i in range(1, 6)}
        for row in distribution:
            distribution_dict[row["rating"]] = row["count"]

        return {
            "average": round(float(stats["average"]), 1) if stats else 0.0,
            "total": stats["total"] if stats else 0,
            "distribution": distribution_dict
        }


def _update_skill_rating_stats(conn, skill_id: int):
    """更新技能的评分统计字段"""
    stats = conn.execute(
        """
        SELECT
            COALESCE(AVG(rating), 0) as average,
            COUNT(*) as total
        FROM skill_ratings
        WHERE skill_id = %s
        """,
        (skill_id,)
    ).fetchone()

    if stats:
        conn.execute(
            "UPDATE skills SET rating_average = %s, rating_count = %s WHERE id = %s",
            (round(float(stats["average"]), 1), stats["total"], skill_id)
        )


def add_comment(skill_id: int, user_id: int, content: str, rating_id: Optional[int] = None) -> Dict[str, Any]:
    """添加评论

    Args:
        skill_id: 技能ID
        user_id: 用户ID
        content: 评论内容（限500字）
        rating_id: 关联的评分ID

    Returns:
        操作结果
    """
    if len(content) > 500:
        return {"success": False, "error": "评论内容不能超过500字"}

    if len(content.strip()) == 0:
        return {"success": False, "error": "评论内容不能为空"}

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skill_comments (skill_id, user_id, content, rating_id)
            VALUES (%s, %s, %s, %s)
            """,
            (skill_id, user_id, content, rating_id)
        )
        comment_id = cursor.lastrowid

        # 更新评论计数
        conn.execute(
            "UPDATE skills SET comment_count = comment_count + 1 WHERE id = %s",
            (skill_id,)
        )

        conn.commit()

        return {
            "success": True,
            "comment_id": comment_id,
            "content": content
        }


def get_skill_comments(skill_id: int, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """获取技能的评论列表

    Args:
        skill_id: 技能ID
        page: 页码
        per_page: 每页数量

    Returns:
        评论列表和分页信息
    """
    with get_connection() as conn:
        # 获取总数
        total_row = conn.execute(
            "SELECT COUNT(*) as total FROM skill_comments WHERE skill_id = %s AND is_deleted = 0",
            (skill_id,)
        ).fetchone()
        total = total_row["total"] if total_row else 0

        # 获取评论列表
        offset = (page - 1) * per_page
        comments = conn.execute(
            """
            SELECT
                c.id, c.content, c.created_at, c.updated_at,
                c.rating_id, u.employee_id,
                r.rating
            FROM skill_comments c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN skill_ratings r ON c.rating_id = r.id
            WHERE c.skill_id = %s AND c.is_deleted = 0
            ORDER BY c.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (skill_id, per_page, offset)
        ).fetchall()

        return {
            "comments": [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "author": row["employee_id"],
                    "rating": row["rating"]
                }
                for row in comments
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0
        }


def delete_comment(comment_id: int, user_id: int) -> bool:
    """删除评论（软删除）

    Args:
        comment_id: 评论ID
        user_id: 用户ID（只能删除自己的评论）

    Returns:
        是否成功
    """
    with get_connection() as conn:
        # 检查评论是否存在且属于该用户
        comment = conn.execute(
            "SELECT skill_id FROM skill_comments WHERE id = %s AND user_id = %s AND is_deleted = 0",
            (comment_id, user_id)
        ).fetchone()

        if not comment:
            return False

        # 软删除
        conn.execute(
            "UPDATE skill_comments SET is_deleted = 1 WHERE id = %s",
            (comment_id,)
        )

        # 更新评论计数
        conn.execute(
            "UPDATE skills SET comment_count = GREATEST(0, comment_count - 1) WHERE id = %s",
            (comment["skill_id"],)
        )

        conn.commit()
        return True


# ============================================
# 搜索历史
# ============================================

def migrate_add_search_features():
    """迁移：添加搜索历史表"""
    with get_connection() as conn:
        # 创建 search_history 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                query VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                INDEX idx_user_created (user_id, created_at DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()
        logger.info("Migration: search_features migration completed")


def add_search_history(user_id: int, query: str) -> None:
    """添加搜索历史

    Args:
        user_id: 用户ID
        query: 搜索关键词
    """
    if not query or len(query.strip()) == 0:
        return

    with get_connection() as conn:
        # 检查是否已存在相同搜索词
        existing = conn.execute(
            """
            SELECT id FROM search_history
            WHERE user_id = %s AND query = %s
            """,
            (user_id, query.strip())
        ).fetchone()

        if existing:
            # 更新时间戳
            conn.execute(
                "UPDATE search_history SET created_at = CURRENT_TIMESTAMP WHERE id = %s",
                (existing["id"],)
            )
        else:
            # 新增记录
            conn.execute(
                "INSERT INTO search_history (user_id, query) VALUES (%s, %s)",
                (user_id, query.strip())
            )

        conn.commit()


def get_search_history(user_id: int, limit: int = 10) -> List[str]:
    """获取用户搜索历史

    Args:
        user_id: 用户ID
        limit: 最大返回数量

    Returns:
        搜索历史列表
    """
    with get_connection() as conn:
        # 使用 GROUP BY 来获取唯一的 query 并按最新时间排序
        # 修复 MySQL 中 "DISTINCT 与 ORDER BY 列不在 SELECT 列表中" 的不兼容问题
        rows = conn.execute(
            """
            SELECT query, MAX(created_at) as latest_created
            FROM search_history
            WHERE user_id = %s
            GROUP BY query
            ORDER BY latest_created DESC
            LIMIT %s
            """,
            (user_id, limit)
        ).fetchall()

        return [row["query"] for row in rows]


def clear_search_history(user_id: int) -> None:
    """清空用户搜索历史

    Args:
        user_id: 用户ID
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM search_history WHERE user_id = %s", (user_id,))
        conn.commit()


# ============================================
# 分类系统
# ============================================

def migrate_add_category_system():
    """迁移：添加分类系统表和 skills 表相关字段"""
    with get_connection() as conn:
        # 创建 categories 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(50) NOT NULL UNIQUE,
                slug VARCHAR(50) NOT NULL UNIQUE,
                icon VARCHAR(50),
                sort_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_slug (slug),
                INDEX idx_sort (sort_order)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 初始化分类数据
        categories_data = [
            ('前端开发', 'frontend', 'code', 1),
            ('后端开发', 'backend', 'server', 2),
            ('DevOps', 'devops', 'git-branch', 3),
            ('安全', 'security', 'shield', 4),
            ('数据工程', 'data', 'database', 5),
            ('通用工具', 'general', 'tool', 6),
        ]

        for name, slug, icon, sort_order in categories_data:
            conn.execute(
                """
                INSERT IGNORE INTO categories (name, slug, icon, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                (name, slug, icon, sort_order)
            )

        # 给 skills 表添加分类和统计字段
        cursor = conn._conn.cursor()
        cursor.execute("DESCRIBE skills")
        columns = [row["Field"] for row in cursor.fetchall()]

        if "category_id" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN category_id INT DEFAULT NULL")
            logger.info("Migration: Added category_id column to skills table")

        if "view_count" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN view_count INT DEFAULT 0")
            logger.info("Migration: Added view_count column to skills table")

        if "screenshots" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN screenshots TEXT DEFAULT NULL")
            logger.info("Migration: Added screenshots column to skills table")

        if "usage_example" not in columns:
            conn.execute("ALTER TABLE skills ADD COLUMN usage_example TEXT DEFAULT NULL")
            logger.info("Migration: Added usage_example column to skills table")

        # 添加分类索引
        cursor = conn._conn.cursor()
        create_index_if_not_exists(
            cursor,
            "skills",
            "idx_skills_category",
            "CREATE INDEX idx_skills_category ON skills(category_id)"
        )

        conn.commit()
        logger.info("Migration: category_system migration completed")


def get_categories() -> List[Dict[str, Any]]:
    """获取所有分类

    Returns:
        分类列表
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, slug, icon, sort_order
            FROM categories
            ORDER BY sort_order
            """
        ).fetchall()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "icon": row["icon"],
                "sort_order": row["sort_order"]
            }
            for row in rows
        ]


def get_category_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """根据 slug 获取分类

    Args:
        slug: 分类 slug

    Returns:
        分类信息或 None
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, slug, icon, sort_order FROM categories WHERE slug = %s",
            (slug,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "icon": row["icon"],
                "sort_order": row["sort_order"]
            }
        return None


def increment_skill_view_count(skill_id: int) -> None:
    """增加技能浏览次数

    Args:
        skill_id: 技能ID
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE skills SET view_count = view_count + 1 WHERE id = %s",
            (skill_id,)
        )
        conn.commit()


def update_skill_category(skill_id: int, category_id: Optional[int]) -> bool:
    """更新技能分类

    Args:
        skill_id: 技能ID
        category_id: 分类ID

    Returns:
        是否成功
    """
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE skills SET category_id = %s WHERE id = %s",
            (category_id, skill_id)
        )
        conn.commit()
        return result.rowcount > 0


def search_skills(
    query: str,
    category_slug: Optional[str] = None,
    source_type: Optional[str] = None,
    sort_by: str = "relevance",
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """高级搜索技能

    Args:
        query: 搜索关键词
        category_slug: 分类 slug
        source_type: 来源类型
        sort_by: 排序方式 (relevance, downloads, rating, newest)
        page: 页码
        per_page: 每页数量

    Returns:
        搜索结果和分页信息
    """
    with get_connection() as conn:
        # 构建基础查询
        base_query = """
            FROM skills s
            LEFT JOIN categories c ON s.category_id = c.id
            JOIN users u ON s.uploader_id = u.id
            WHERE s.status = 'approved' AND s.is_active = 1
        """
        params = []

        # 搜索条件
        if query and query.strip():
            base_query += " AND (s.skill_name LIKE %s OR s.description LIKE %s)"
            search_term = f"%{query.strip()}%"
            params.extend([search_term, search_term])

        # 分类过滤
        if category_slug:
            base_query += " AND c.slug = %s"
            params.append(category_slug)

        # 来源类型过滤
        if source_type:
            base_query += " AND s.source_type = %s"
            params.append(source_type)

        # 获取总数
        count_query = f"SELECT COUNT(*) as total {base_query}"
        total_row = conn.execute(count_query, params).fetchone()
        total = total_row["total"] if total_row else 0

        # 排序
        order_clause = ""
        if sort_by == "relevance" and query:
            # 简单的相关性排序：名称匹配优先
            order_clause = "ORDER BY CASE WHEN s.skill_name LIKE %s THEN 0 ELSE 1 END, s.rating_average DESC"
            params.append(f"%{query.strip()}%")
        elif sort_by == "downloads":
            order_clause = "ORDER BY s.view_count DESC"
        elif sort_by == "rating":
            order_clause = "ORDER BY s.rating_average DESC, s.rating_count DESC"
        elif sort_by == "newest":
            order_clause = "ORDER BY s.uploaded_at DESC"
        else:
            order_clause = "ORDER BY s.rating_average DESC"

        # 分页
        offset = (page - 1) * per_page
        data_query = f"""
            SELECT
                s.id, s.skill_name, s.version, s.description, s.source_type,
                s.rating_average, s.rating_count, s.comment_count, s.view_count,
                s.uploaded_at, c.name as category_name, c.slug as category_slug,
                u.employee_id as author
            {base_query}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])

        rows = conn.execute(data_query, params).fetchall()

        return {
            "skills": [
                {
                    "id": row["id"],
                    "name": row["skill_name"],
                    "version": row["version"],
                    "description": row["description"],
                    "source_type": row["source_type"],
                    "rating_average": float(row["rating_average"]) if row["rating_average"] else 0.0,
                    "rating_count": row["rating_count"],
                    "comment_count": row["comment_count"],
                    "view_count": row["view_count"],
                    "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                    "category": {
                        "name": row["category_name"],
                        "slug": row["category_slug"]
                    } if row["category_name"] else None,
                    "author": row["author"]
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0
        }


def get_search_suggestions(query: str, limit: int = 5) -> List[str]:
    """获取搜索建议

    Args:
        query: 搜索关键词
        limit: 最大返回数量

    Returns:
        建议列表
    """
    if not query or len(query.strip()) < 2:
        return []

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT skill_name, MAX(rating_average) as rating_average, MAX(view_count) as view_count
            FROM skills
            WHERE status = 'approved' AND is_active = 1
              AND skill_name LIKE %s
            GROUP BY skill_name
            ORDER BY rating_average DESC, view_count DESC
            LIMIT %s
            """,
            (f"%{query.strip()}%", limit)
        ).fetchall()

        return [row["skill_name"] for row in rows]
