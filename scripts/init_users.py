#!/usr/bin/env python3
"""
Initialize test users in the database.

This script creates test users for development and testing purposes.
"""

import sys
from pathlib import Path

# Add parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, get_connection


def init_users():
    """Initialize test users in the database."""
    # Ensure database tables exist
    print("Initializing database...")
    init_db()
    print("Database initialized.")

    # Define test users
    test_users = [
        {
            "employee_id": "w00000001",
            "api_key": "sk-test-admin-key-1",
            "role": "admin"
        },
        {
            "employee_id": "w00000002",
            "api_key": "sk-test-user-key-1",
            "role": "user"
        },
        {
            "employee_id": "w00000003",
            "api_key": "sk-test-user-key-2",
            "role": "user"
        }
    ]

    print("\nCreating test users...")
    created_count = 0
    skipped_count = 0

    with get_connection() as conn:
        for user_data in test_users:
            employee_id = user_data["employee_id"]

            # Check if user already exists
            cursor = conn.execute(
                "SELECT id FROM users WHERE employee_id = ?",
                (employee_id,)
            )
            existing = cursor.fetchone()

            if existing:
                print(f"  [*] User {employee_id} already exists, skipping...")
                skipped_count += 1
            else:
                # Insert the user
                conn.execute(
                    """
                    INSERT INTO users (employee_id, api_key, role)
                    VALUES (?, ?, ?)
                    """,
                    (user_data["employee_id"], user_data["api_key"], user_data["role"])
                )
                conn.commit()
                print(f"  + Created user: {employee_id} ({user_data['role']})")
                created_count += 1

    print(f"\nSummary:")
    print(f"  Created: {created_count} users")
    print(f"  Skipped: {skipped_count} users")
    print(f"  Total:   {len(test_users)} test users configured")

    # Print test credentials
    print("\n" + "="*60)
    print("TEST CREDENTIALS")
    print("="*60)
    print("\nAdmin User:")
    print("  Employee ID: w00000001")
    print("  API Key:     sk-test-admin-key-1")
    print("  Role:        admin")
    print("\nRegular Users:")
    print("  Employee ID: w00000002")
    print("  API Key:     sk-test-user-key-1")
    print("  Role:        user")
    print("\n  Employee ID: w00000003")
    print("  API Key:     sk-test-user-key-2")
    print("  Role:        user")
    print("="*60)


if __name__ == "__main__":
    init_users()
