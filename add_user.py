#!/usr/bin/env python3
"""
Add a test user to the database.
"""

from database import get_connection

def add_user():
    """Add test user to database."""
    with get_connection() as conn:
        # Check if user already exists
        existing = conn.execute(
            "SELECT id FROM users WHERE employee_id = ?",
            ('w00545471',)
        ).fetchone()

        if existing:
            print(f"User w00545471 already exists (ID: {existing[0]})")
            return

        # Insert new user
        conn.execute(
            "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
            ('w00545471', 'sk-123', 'admin')
        )
        conn.commit()

        print("User added successfully!")
        print("  Employee ID: w00545471")
        print("  API KEY: sk-123")
        print("  Role: admin")

if __name__ == "__main__":
    add_user()
