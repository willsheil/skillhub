import pytest
from services.gitea.gitea_integration import create_push_task
from database import get_connection, init_db


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    init_db()
    # Clean up any existing test data
    with get_connection() as conn:
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-gitea-%'")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-gitea-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-gitea-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-gitea-%'")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-gitea-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-gitea-%'")
        conn.commit()


def test_create_push_task():
    # Create a test user first
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES (%s, %s, %s, 1, 0)
        """, ("test-gitea-user", "test-key", "user"))
        user_id = cursor.lastrowid
        conn.commit()

    # Create a test skill with unique name
    skill_name = "test-gitea-push-skill"
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (skill_name, '1.0.0', 'test.zip', user_id, 'approved'))
        skill_id = cursor.lastrowid
        conn.commit()

    # Create push task - this will call get_skill_by_id which uses its own connection
    task_id = create_push_task(skill_id)

    assert task_id is not None
    assert task_id > 0

    # Verify task was created
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM gitea_push_tasks WHERE id = %s
        """, (task_id,)).fetchone()

        assert row is not None
        assert row['skill_name'] == skill_name
        assert row['version'] == '1.0.0'
        assert row['status'] == 'pending'
