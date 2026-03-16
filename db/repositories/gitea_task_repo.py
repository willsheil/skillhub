"""
Gitea task repository - Database operations for Gitea push tasks.

Provides methods for managing background push tasks to Gitea repository.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from db.connection import get_connection
from db.models import GiteaPushTask
from core.constants import TaskStatus

logger = logging.getLogger(__name__)


class GiteaTaskRepository:
    """Repository for Gitea push task database operations."""

    @staticmethod
    def create(skill_id: int) -> GiteaPushTask:
        """Create a new push task.

        Args:
            skill_id: Skill ID to push

        Returns:
            Created GiteaPushTask object
        """
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO gitea_push_tasks (skill_id, status) VALUES (%s, %s)",
                (skill_id, TaskStatus.PENDING.value)
            )
            conn.commit()

            cursor = conn.execute("SELECT LAST_INSERT_ID() as id")
            task_id = cursor.fetchone()['id']

            cursor = conn.execute(
                "SELECT * FROM gitea_push_tasks WHERE id = %s",
                (task_id,)
            )
            return GiteaPushTask(**cursor.fetchone())

    @staticmethod
    def get_by_id(task_id: int) -> Optional[GiteaPushTask]:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            GiteaPushTask object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM gitea_push_tasks WHERE id = %s",
                (task_id,)
            )
            row = cursor.fetchone()
            if row:
                return GiteaPushTask(**row)
            return None

    @staticmethod
    def get_pending(limit: int = 10) -> List[GiteaPushTask]:
        """Get pending tasks.

        Args:
            limit: Max results

        Returns:
            List of pending GiteaPushTask objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM gitea_push_tasks
                   WHERE status IN (%s, %s)
                   ORDER BY created_at ASC LIMIT %s""",
                (TaskStatus.PENDING.value, TaskStatus.RETRY_PENDING.value, limit)
            )
            return [GiteaPushTask(**row) for row in cursor.fetchall()]

    @staticmethod
    def reserve_task(worker_id: str) -> Optional[GiteaPushTask]:
        """Reserve a task for processing (with row locking).

        Args:
            worker_id: Worker identifier

        Returns:
            Reserved GiteaPushTask object or None
        """
        with get_connection() as conn:
            # Use SELECT FOR UPDATE to reserve task
            cursor = conn.execute(
                """SELECT * FROM gitea_push_tasks
                   WHERE status IN (%s, %s)
                   AND retry_count < 3
                   ORDER BY created_at ASC
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED""",
                (TaskStatus.PENDING.value, TaskStatus.RETRY_PENDING.value)
            )
            row = cursor.fetchone()
            if not row:
                return None

            task_id = row['id']

            # Update task status
            conn.execute(
                """UPDATE gitea_push_tasks
                   SET status = %s, worker_id = %s, started_at = %s
                   WHERE id = %s""",
                (TaskStatus.RESERVED.value, worker_id, datetime.now(), task_id)
            )
            conn.commit()

            # Return updated task
            cursor = conn.execute(
                "SELECT * FROM gitea_push_tasks WHERE id = %s",
                (task_id,)
            )
            return GiteaPushTask(**cursor.fetchone())

    @staticmethod
    def mark_success(task_id: int, commit_hash: str) -> bool:
        """Mark task as successful.

        Args:
            task_id: Task ID
            commit_hash: Git commit hash

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                """UPDATE gitea_push_tasks
                   SET status = %s, commit_hash = %s, completed_at = %s
                   WHERE id = %s""",
                (TaskStatus.SUCCESS.value, commit_hash, datetime.now(), task_id)
            )
            conn.commit()
            return True

    @staticmethod
    def mark_failed(task_id: int, error_message: str) -> bool:
        """Mark task as failed.

        Args:
            task_id: Task ID
            error_message: Error message

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                """UPDATE gitea_push_tasks
                   SET status = %s, error_message = %s, completed_at = %s
                   WHERE id = %s""",
                (TaskStatus.FAILED.value, error_message, datetime.now(), task_id)
            )
            conn.commit()
            return True

    @staticmethod
    def mark_retry_pending(task_id: int) -> bool:
        """Mark task for retry.

        Args:
            task_id: Task ID

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                """UPDATE gitea_push_tasks
                   SET status = %s, retry_count = retry_count + 1,
                   worker_id = NULL, started_at = NULL
                   WHERE id = %s""",
                (TaskStatus.RETRY_PENDING.value, task_id)
            )
            conn.commit()
            return True

    @staticmethod
    def get_by_skill(skill_id: int) -> List[GiteaPushTask]:
        """Get all tasks for a skill.

        Args:
            skill_id: Skill ID

        Returns:
            List of GiteaPushTask objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM gitea_push_tasks
                   WHERE skill_id = %s
                   ORDER BY created_at DESC""",
                (skill_id,)
            )
            return [GiteaPushTask(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get task statistics.

        Returns:
            Dict with counts by status
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT status, COUNT(*) as count
                   FROM gitea_push_tasks
                   GROUP BY status"""
            )
            return {row['status']: row['count'] for row in cursor.fetchall()}

    @staticmethod
    def delete_old_completed(days: int = 7) -> int:
        """Delete old completed tasks.

        Args:
            days: Delete tasks completed more than N days ago

        Returns:
            Number of deleted tasks
        """
        cutoff = datetime.now() - timedelta(days=days)
        with get_connection() as conn:
            conn.execute(
                """DELETE FROM gitea_push_tasks
                   WHERE status IN (%s, %s) AND completed_at < %s""",
                (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value, cutoff)
            )
            conn.commit()
            return conn.execute("SELECT ROW_COUNT()").fetchone()['ROW_COUNT()']
