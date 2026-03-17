from database import init_db, get_connection

init_db()

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT id, employee_id, api_key, role, status FROM users')
    users = cursor.fetchall()

    print('Users in database:')
    for u in users:
        print(f'ID: {u["id"]}, Employee: {u["employee_id"]}, API Key: {u["api_key"]}, Role: {u["role"]}, Status: {u["status"]}')
