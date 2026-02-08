import pytest
from gitea_integration import create_push_task
from database import get_connection

def test_create_push_task():
    # Create a test skill first
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES ('test-skill', '1.0.0', 'test.zip', 1, 'approved')
        """)
        skill_id = cursor.lastrowid
        conn.commit()

    # Create push task
    task_id = create_push_task(skill_id)

    assert task_id is not None
    assert task_id > 0

    # Verify task was created
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM gitea_push_tasks WHERE id = %s
        """, (task_id,)).fetchone()

        assert row is not None
        assert row['skill_name'] == 'test-skill'
        assert row['version'] == '1.0.0'
        assert row['status'] == 'pending'
