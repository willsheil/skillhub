#!/usr/bin/env python3
"""
Ensure only 'admin' is the admin user, all others are regular users.
"""

from database import get_connection

def fix_admin_role():
    """Fix user roles so only 'admin' is admin."""
    with get_connection() as conn:
        # Set all users to 'user' role except 'admin'
        conn.execute(
            "UPDATE users SET role = 'user' WHERE employee_id != ?",
            ('admin',)
        )

        # Ensure admin user exists and has admin role
        admin_user = conn.execute(
            "SELECT * FROM users WHERE employee_id = 'admin'"
        ).fetchone()

        if not admin_user:
            # Create admin user if doesn't exist
            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
                ('admin', 'admin', 'admin')
            )
            print("Created new admin user")

        conn.commit()

        # Display all users
        print("\nAll users in database:")
        users = conn.execute("SELECT employee_id, api_key, role FROM users ORDER BY employee_id").fetchall()
        for user in users:
            print(f"  {user[0]:<15} | {user[1]:<20} | {user[2]:<10}")

if __name__ == "__main__":
    fix_admin_role()
