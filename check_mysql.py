#!/usr/bin/env python3
"""
Check MySQL connection and create database if needed.
"""

import pymysql

try:
    # Connect to MySQL server (without database specified)
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root',
        charset='utf8mb4'
    )
    print("Connected to MySQL server successfully!")

    # Check if Skill database exists
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES LIKE 'Skill'")
    result = cursor.fetchone()

    if result:
        print("Database 'Skill' already exists.")
    else:
        print("Creating database 'Skill'...")
        cursor.execute("CREATE DATABASE Skill CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("Database 'Skill' created successfully!")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error connecting to MySQL: {e}")
    print("\nPlease make sure:")
    print("1. MySQL server is running on 127.0.0.1")
    print("2. Username is 'root' and password is 'root'")
    print("3. MySQL client library is installed")
