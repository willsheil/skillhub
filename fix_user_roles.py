#!/usr/bin/env python3
"""
Update user roles: w00545471 should be a regular user, admin should be the only admin.
"""

from database import get_connection

def update_user_roles():
    """Update user roles correctly."""
    with get_connection() as conn:
        # Update w00545471 to regular user
        conn.execute(
            "UPDATE users SET role = 'user' WHERE employee_id = ?",
            ('w00545471',)
        )

        # Check if admin user exists
        admin_user = conn.execute(
            "SELECT * FROM users WHERE employee_id = 'admin'"
        ).fetchone()

        if admin_user:
            # Update admin user to ensure role is admin
            conn.execute(
                "UPDATE users SET role = 'admin' WHERE employee_id = 'admin'"
            )
            print(f"Updated admin user (ID: {admin_user[0]})")
        else:
            # Create admin user if doesn't exist
            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
                ('admin', 'admin', 'admin')
            )
            print("Created new admin user")

        conn.commit()

        # Display all users
        print("\nAll users in database:")
        users = conn.execute("SELECT employee_id, role FROM users").fetchall()
        for user in users:
            print(f"  - {user[0]}: {user[1]}")

if __name__ == "__main__":
    update_user_roles()
