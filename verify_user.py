#!/usr/bin/env python3
from database import get_connection

with get_connection() as conn:
    user = conn.execute('SELECT * FROM users WHERE employee_id = ?', ('w00545471',)).fetchone()
    if user:
        print("User found:")
        print(f"  ID: {user[0]}")
        print(f"  Employee ID: {user[1]}")
        print(f"  API KEY: {user[2]}")
        print(f"  Role: {user[3]}")
        print(f"  Created: {user[4]}")
        print(f"  Last Login: {user[5]}")
    else:
        print("User not found")
