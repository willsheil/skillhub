#!/usr/bin/env python3
"""
Initialize test users for the skill registry.

Run this script to create test user accounts for development and testing.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, create_user


def main():
    """Initialize database and create test users."""
    print("Initializing database...")
    init_db()

    print("\nCreating test users...")

    # Create admin user
    try:
        admin_id = create_user("admin001", "admin_key_001", role="admin")
        print("[OK] Created admin user: employee_id=admin001, api_key=admin_key_001")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            print("[INFO] Admin user already exists: employee_id=admin001")
        else:
            raise

    # Create regular users
    try:
        user1_id = create_user("test001", "test_key_001", role="user")
        print("[OK] Created test user: employee_id=test001, api_key=test_key_001")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            print("[INFO] Test user already exists: employee_id=test001")
        else:
            raise

    try:
        user2_id = create_user("test002", "test_key_002", role="user")
        print("[OK] Created test user: employee_id=test002, api_key=test_key_002")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            print("[INFO] Test user already exists: employee_id=test002")
        else:
            raise

    print("\n" + "=" * 60)
    print("Test users initialized successfully!")
    print("=" * 60)
    print("\nYou can now log in with these credentials:")
    print("\nAdmin account:")
    print("  URL: http://localhost:28000/login")
    print("  Employee ID: admin001")
    print("  API Key: admin_key_001")
    print("\nUser accounts:")
    print("  Employee ID: test001")
    print("  API Key: test_key_001")
    print("\n  Employee ID: test002")
    print("  API Key: test_key_002")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
