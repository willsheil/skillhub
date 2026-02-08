import logging
from database import get_connection

logger = logging.getLogger(__name__)

def create_push_task(skill_id: int) -> int:
    """Create a Gitea push task for an approved skill.

    Args:
        skill_id: ID of the approved skill

    Returns:
        ID of the created push task
    """
    from database import get_skill_by_id

    skill = get_skill_by_id(skill_id)
    if not skill:
        raise ValueError(f"Skill {skill_id} not found")

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO gitea_push_tasks
            (skill_id, skill_name, version, status)
            VALUES (%s, %s, %s, 'pending')
        """, (skill_id, skill['skill_name'], skill['version']))
        conn.commit()

        task_id = cursor.lastrowid
        logger.info(f"Created Gitea push task {task_id} for skill {skill['skill_name']}-{skill['version']}")

        return task_id

def get_pending_tasks(limit: int = 10):
    """Get pending push tasks.

    Args:
        limit: Maximum number of tasks to retrieve

    Returns:
        List of task dictionaries
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT t.*, s.filename, s.uploader_id
            FROM gitea_push_tasks t
            JOIN skills s ON t.skill_id = s.id
            WHERE t.status = 'pending'
            ORDER BY t.created_at ASC
            LIMIT %s
        """, (limit,)).fetchall()

        return rows

def update_push_status(task_id: int, status: str, **kwargs):
    """Update push task status and metadata.

    Args:
        task_id: ID of the push task
        status: New status ('pending', 'pushing', 'success', 'failed')
        **kwargs: Additional fields (retry_count, error_message, commit_hash, gitea_path)
    """
    valid_statuses = ['pending', 'pushing', 'success', 'failed']
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}")

    updates = ["status = %s"]
    values = [status]

    if 'retry_count' in kwargs:
        updates.append("retry_count = %s")
        values.append(kwargs['retry_count'])

    if 'error_message' in kwargs:
        updates.append("error_message = %s")
        values.append(kwargs['error_message'])

    if 'commit_hash' in kwargs:
        updates.append("commit_hash = %s")
        values.append(kwargs['commit_hash'])

    if 'gitea_path' in kwargs:
        updates.append("gitea_path = %s")
        values.append(kwargs['gitea_path'])

    # Update timestamp based on status
    if status == 'pushing' and 'started_at' not in kwargs:
        updates.append("started_at = CURRENT_TIMESTAMP")
    elif status in ['success', 'failed']:
        updates.append("completed_at = CURRENT_TIMESTAMP")

    values.append(task_id)

    with get_connection() as conn:
        conn.execute(f"""
            UPDATE gitea_push_tasks
            SET {', '.join(updates)}
            WHERE id = %s
        """, values)
        conn.commit()

        logger.debug(f"Updated task {task_id} to {status}")
