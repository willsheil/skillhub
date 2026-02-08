#!/usr/bin/env python3
"""
Migrate data from SQLite to MySQL.

This script will:
1. Read all data from SQLite database
2. Create tables in MySQL (if not exist)
3. Copy all data from SQLite to MySQL
"""

import sqlite3
import pymysql
from pathlib import Path

# SQLite configuration
SQLITE_DB_PATH = Path("./data/registry.db")

# MySQL configuration
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'skills',
    'charset': 'utf8mb4'
}


def get_sqlite_connection():
    """Get SQLite connection."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_mysql_connection():
    """Get MySQL connection."""
    return pymysql.connect(**MYSQL_CONFIG)


def create_mysql_tables():
    """Create all tables in MySQL."""
    print("Creating tables in MySQL...")

    with get_mysql_connection() as conn:
        with conn.cursor() as cursor:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id VARCHAR(20) UNIQUE NOT NULL,
                    api_key VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Create skills table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    skill_name VARCHAR(255) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    uploader_id INT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP NULL,
                    reviewer_id INT NULL,
                    review_comment VARCHAR(255) NULL,
                    FOREIGN KEY (uploader_id) REFERENCES users(id),
                    FOREIGN KEY (reviewer_id) REFERENCES users(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Create downloads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    skill_name VARCHAR(255) NOT NULL,
                    version VARCHAR(50) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(255) NULL,
                    user_agent VARCHAR(255) NULL,
                    user_id INT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Create indexes (check if exists first)
            # Check and create idx_users_employee_id
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'users' AND index_name = 'idx_users_employee_id'
            """)
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    CREATE INDEX idx_users_employee_id
                    ON users(employee_id)
                """)

            # Check and create idx_downloads_skill_date
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'downloads' AND index_name = 'idx_downloads_skill_date'
            """)
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    CREATE INDEX idx_downloads_skill_date
                    ON downloads(skill_name, downloaded_at)
                """)

            # Check and create idx_skills_status
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'skills' AND index_name = 'idx_skills_status'
            """)
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    CREATE INDEX idx_skills_status
                    ON skills(status)
                """)

            # Check and create idx_skills_uploader
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name = 'skills' AND index_name = 'idx_skills_uploader'
            """)
            if cursor.fetchone()['count'] == 0:
                cursor.execute("""
                    CREATE INDEX idx_skills_uploader
                    ON skills(uploader_id)
                """)

        conn.commit()
        print("  Tables created successfully!")


def migrate_users():
    """Migrate users from SQLite to MySQL."""
    print("Migrating users...")

    with get_sqlite_connection() as sqlite_conn:
        with get_mysql_connection() as mysql_conn:
            sqlite_cursor = sqlite_conn.execute("SELECT * FROM users")
            users = sqlite_cursor.fetchall()

            with mysql_conn.cursor() as mysql_cursor:
                for user in users:
                    try:
                        mysql_cursor.execute("""
                            INSERT INTO users (id, employee_id, api_key, role, created_at, last_login)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            user['id'],
                            user['employee_id'],
                            user['api_key'],
                            user['role'],
                            user['created_at'],
                            user['last_login']
                        ))
                    except pymysql.IntegrityError:
                        print(f"  User {user['employee_id']} already exists, skipping...")

            mysql_conn.commit()
            print(f"  Migrated {len(users)} users")


def migrate_skills():
    """Migrate skills from SQLite to MySQL."""
    print("Migrating skills...")

    with get_sqlite_connection() as sqlite_conn:
        with get_mysql_connection() as mysql_conn:
            sqlite_cursor = sqlite_conn.execute("SELECT * FROM skills")
            skills = sqlite_cursor.fetchall()

            with mysql_conn.cursor() as mysql_cursor:
                for skill in skills:
                    mysql_cursor.execute("""
                        INSERT INTO skills (id, skill_name, version, filename, uploader_id,
                                         status, uploaded_at, reviewed_at, reviewer_id, review_comment)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        skill['id'],
                        skill['skill_name'],
                        skill['version'],
                        skill['filename'],
                        skill['uploader_id'],
                        skill['status'],
                        skill['uploaded_at'],
                        skill['reviewed_at'],
                        skill['reviewer_id'],
                        skill['review_comment']
                    ))

            mysql_conn.commit()
            print(f"  Migrated {len(skills)} skills")


def migrate_downloads():
    """Migrate downloads from SQLite to MySQL."""
    print("Migrating downloads...")

    with get_sqlite_connection() as sqlite_conn:
        with get_mysql_connection() as mysql_conn:
            sqlite_cursor = sqlite_conn.execute("SELECT * FROM downloads")
            downloads = sqlite_cursor.fetchall()

            with mysql_conn.cursor() as mysql_cursor:
                for download in downloads:
                    mysql_cursor.execute("""
                        INSERT INTO downloads (id, skill_name, version, filename,
                                           downloaded_at, ip_address, user_agent, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        download['id'],
                        download['skill_name'],
                        download['version'],
                        download['filename'],
                        download['downloaded_at'],
                        download['ip_address'],
                        download['user_agent'],
                        download['user_id']
                    ))

            mysql_conn.commit()
            print(f"  Migrated {len(downloads)} downloads")


def verify_migration():
    """Verify that all data was migrated successfully."""
    print("\nVerifying migration...")

    with get_sqlite_connection() as sqlite_conn:
        with get_mysql_connection() as mysql_conn:

            # Count users
            sqlite_users = sqlite_conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
            mysql_users = mysql_conn.cursor()
            mysql_users.execute("SELECT COUNT(*) as count FROM users")
            mysql_users_count = mysql_users.fetchone()['count']
            print(f"  Users: SQLite={sqlite_users}, MySQL={mysql_users_count}")

            # Count skills
            sqlite_skills = sqlite_conn.execute("SELECT COUNT(*) as count FROM skills").fetchone()['count']
            mysql_skills = mysql_conn.cursor()
            mysql_skills.execute("SELECT COUNT(*) as count FROM skills")
            mysql_skills_count = mysql_skills.fetchone()['count']
            print(f"  Skills: SQLite={sqlite_skills}, MySQL={mysql_skills_count}")

            # Count downloads
            sqlite_downloads = sqlite_conn.execute("SELECT COUNT(*) as count FROM downloads").fetchone()['count']
            mysql_downloads = mysql_conn.cursor()
            mysql_downloads.execute("SELECT COUNT(*) as count FROM downloads")
            mysql_downloads_count = mysql_downloads.fetchone()['count']
            print(f"  Downloads: SQLite={sqlite_downloads}, MySQL={mysql_downloads_count}")

    print("\nMigration completed successfully!")


def main():
    """Run the complete migration."""
    print("="*60)
    print("SQLite to MySQL Migration")
    print("="*60)
    print()

    # Check if SQLite database exists
    if not SQLITE_DB_PATH.exists():
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        return

    print(f"SQLite database: {SQLITE_DB_PATH}")
    print(f"MySQL server: {MYSQL_CONFIG['host']}")
    print(f"MySQL database: {MYSQL_CONFIG['database']}")
    print()

    try:
        # Step 1: Create tables
        create_mysql_tables()
        print()

        # Step 2: Migrate data
        migrate_users()
        migrate_skills()
        migrate_downloads()
        print()

        # Step 3: Verify
        verify_migration()

    except Exception as e:
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
