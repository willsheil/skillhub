import logging
from typing import Optional, Dict
from database import get_connection

logger = logging.getLogger(__name__)

def create_push_task(skill_id: int) -> int:
    """Create a Gitea push task for an approved skill.

    Args:
        skill_id: ID of the approved skill

    Returns:
        ID of the created push task

    Raises:
        ValueError: If skill not found or task already exists
    """
    from database import get_skill_by_id

    skill = get_skill_by_id(skill_id)
    if not skill:
        raise ValueError(f"Skill {skill_id} not found")

    with get_connection() as conn:
        # Check if there's already a pending task for this skill
        existing = conn.execute("""
            SELECT id FROM gitea_push_tasks
            WHERE skill_id = %s AND status IN ('pending', 'pushing', 'retry_pending')
        """, (skill_id,)).fetchone()

        if existing:
            logger.info(f"Push task already exists for skill {skill_id}, reusing task {existing['id']}")
            return existing['id']

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

    Raises:
        ValueError: If status or field names are invalid
    """
    # Whitelist of valid statuses and fields for security
    valid_statuses = ['pending', 'reserved', 'pushing', 'success', 'failed', 'retry_pending']
    valid_fields = {
        'retry_count': 'retry_count',
        'error_message': 'error_message',
        'commit_hash': 'commit_hash',
        'gitea_path': 'gitea_path',
        'started_at': 'started_at',
        'completed_at': 'completed_at',
        'reserved_at': 'reserved_at',
        'worker_id': 'worker_id'
    }

    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

    # Build update clauses with parameterized queries
    updates = []
    values = []

    # Always update status
    updates.append("status = %s")
    values.append(status)

    # Add optional fields (whitelisted only)
    for key, value in kwargs.items():
        if key not in valid_fields:
            raise ValueError(f"Invalid field: {key}. Must be one of {list(valid_fields.keys())}")
        updates.append(f"{valid_fields[key]} = %s")
        values.append(value)

    # Auto-update timestamps based on status
    if status == 'pushing' and 'started_at' not in kwargs:
        updates.append("started_at = CURRENT_TIMESTAMP")
    elif status in ['success', 'failed'] and 'completed_at' not in kwargs:
        updates.append("completed_at = CURRENT_TIMESTAMP")

    # Add task_id as the last parameter
    values.append(task_id)

    with get_connection() as conn:
        sql = f"""
            UPDATE gitea_push_tasks
            SET {', '.join(updates)}
            WHERE id = %s
        """
        conn.execute(sql, values)
        conn.commit()

        logger.debug(f"Updated task {task_id} to status '{status}'")


def reserve_task(worker_id: str, timeout_seconds: int = 600) -> Optional[Dict]:
    """Atomically reserve a pending task for processing.

    Uses row-level locking (SELECT FOR UPDATE) to prevent multiple workers
    from claiming the same task. This prevents duplicate processing.

    Args:
        worker_id: Unique identifier for the worker (e.g., hostname:pid)
        timeout_seconds: Task timeout in seconds (for stale task detection)

    Returns:
        Task dictionary if reserved, None if no pending tasks available

    Raises:
        ValueError: If worker_id is empty
    """
    if not worker_id:
        raise ValueError("worker_id cannot be empty")

    with get_connection() as conn:
        # Start a transaction for atomic operation
        conn.execute("START TRANSACTION")

        try:
            # Find and lock a pending task (oldest first)
            cursor = conn.execute("""
                SELECT id, skill_id, skill_name, version, filename, retry_count, max_retries
                FROM gitea_push_tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE
            """)
            task = cursor.fetchone()

            if not task:
                # No pending tasks available
                conn.execute("ROLLBACK")
                return None

            task_id = task['id']

            # Mark as reserved with worker info
            conn.execute("""
                UPDATE gitea_push_tasks
                SET status = 'reserved',
                    reserved_at = CURRENT_TIMESTAMP,
                    worker_id = %s
                WHERE id = %s
            """, (worker_id, task_id))

            conn.commit()

            logger.info(
                f"Reserved task {task_id} for worker '{worker_id}'",
                extra={
                    "task_id": task_id,
                    "worker_id": worker_id,
                    "skill_name": task['skill_name']
                }
            )

            return dict(task)

        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error(f"Failed to reserve task: {e}")
            raise


def release_task_reservation(task_id: int, new_status: str = 'pending'):
    """Release a task reservation, returning it to pending or other status.

    Args:
        task_id: ID of the task to release
        new_status: Status to set (default: 'pending')

    Raises:
        ValueError: If status is invalid
    """
    valid_statuses = ['pending', 'retry_pending']
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status for release: {new_status}. Must be one of {valid_statuses}")

    with get_connection() as conn:
        conn.execute("""
            UPDATE gitea_push_tasks
            SET status = %s,
                reserved_at = NULL,
                worker_id = NULL
            WHERE id = %s
        """, (new_status, task_id))
        conn.commit()

        logger.debug(f"Released reservation for task {task_id} to status '{new_status}'")


def cleanup_stale_reservations(timeout_seconds: int = 3600):
    """Release stale task reservations that have timed out.

    Args:
        timeout_seconds: Timeout in seconds (default: 1 hour)

    Returns:
        Number of tasks released
    """
    from datetime import timedelta

    with get_connection() as conn:
        # MySQL syntax for date subtraction
        cursor = conn.execute("""
            UPDATE gitea_push_tasks
            SET status = 'pending',
                reserved_at = NULL,
                worker_id = NULL
            WHERE status = 'reserved'
              AND reserved_at < DATE_SUB(NOW(), INTERVAL %s SECOND)
        """, (timeout_seconds,))

        released_count = cursor.rowcount
        conn.commit()

        if released_count > 0:
            logger.info(
                f"Released {released_count} stale task reservations",
                extra={"released_count": released_count}
            )

        return released_count
