"""
Enhanced Gitea Push Service with improved logic and monitoring.

Improvements:
- Concurrent task processing with semaphore control
- Intelligent retry with exponential backoff
- Priority queue for critical tasks
- Task timeout and cancellation
- Health check and metrics
- Better error classification and recovery
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import time

from gitea_client import GiteaClient, GiteaError, NetworkError
from gitea_integration import get_pending_tasks, update_push_status
from database import get_connection

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """Task status tracking."""
    PENDING = "pending"
    PUSHING = "pushing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class PushTask:
    """Push task data structure."""
    id: int
    skill_id: int
    skill_name: str
    version: str
    filename: str
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime = None
    started_at: Optional[datetime] = None
    timeout_seconds: int = 600  # 10 minutes default

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    @property
    def is_timeout(self) -> bool:
        """Check if task has timed out."""
        if self.started_at is None:
            return False
        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        return elapsed > self.timeout_seconds

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries

    @property
    def age_seconds(self) -> int:
        """Get task age in seconds."""
        return int((datetime.utcnow() - self.created_at).total_seconds())


class GiteaPushServiceV2:
    """Enhanced Gitea push service with concurrent processing and monitoring."""

    def __init__(
        self,
        interval: int = 30,
        max_concurrent_tasks: int = 3,
        retry_base_delay: int = 1,
        retry_max_delay: int = 300,
        health_check_interval: int = 60
    ):
        """Initialize enhanced push service.

        Args:
            interval: Task scan interval in seconds
            max_concurrent_tasks: Maximum concurrent push operations
            retry_base_delay: Base delay for retry in seconds (exponential backoff)
            retry_max_delay: Maximum retry delay in seconds
            health_check_interval: Health check interval in seconds
        """
        self.client = GiteaClient()
        self.interval = interval
        self.max_concurrent_tasks = max_concurrent_tasks
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.health_check_interval = health_check_interval

        self.running = False
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)

        # Metrics tracking
        self.metrics = {
            "tasks_processed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "total_push_time_seconds": 0.0,
            "last_health_check": None,
            "service_start_time": None
        }

    async def process_task(self, task: PushTask) -> Dict:
        """Process a single push task with timeout and retry logic.

        Args:
            task: PushTask instance

        Returns:
            Result dict with status and details
        """
        task_id = task.id
        skill_zip = Path("./plugins") / task.filename

        async with self.semaphore:  # Limit concurrent operations
            # Check for file existence
            if not skill_zip.exists():
                error = f"Skill ZIP not found: {skill_zip}"
                update_push_status(task_id, "failed", error_message=error)
                logger.error(f"Task {task_id} failed: {error}",
                           extra={"task_id": task_id, "skill_name": task.skill_name})
                return {"success": False, "error": error}

            # Update to pushing status
            update_push_status(task_id, "pushing")
            task.started_at = datetime.utcnow()

            try:
                # Create timeout task
                push_task = asyncio.create_task(
                    self._execute_push(task, skill_zip)
                )
                timeout_task = asyncio.create_task(
                    self._timeout_monitor(task, task.timeout_seconds)
                )

                # Wait for either completion or timeout
                done, pending = await asyncio.wait(
                    [push_task, timeout_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for p in pending:
                    p.cancel()
                    try:
                        await p
                    except asyncio.CancelledError:
                        pass

                # Get result
                if push_task in done:
                    result = await push_task
                else:
                    # Timeout occurred
                    result = {
                        "success": False,
                        "error": "Task timeout",
                        "timeout": True
                    }

                # Handle result
                if result["success"]:
                    await self._handle_success(task_id, result)
                else:
                    await self._handle_failure(task, result)

                self.metrics["tasks_processed"] += 1
                return result

            except Exception as e:
                logger.exception(f"Unexpected error processing task {task_id}")
                update_push_status(
                    task_id,
                    "failed",
                    error_message=f"Unexpected error: {str(e)}"
                )
                self.metrics["tasks_failed"] += 1
                return {"success": False, "error": str(e)}

    async def _execute_push(self, task: PushTask, skill_zip: Path) -> Dict:
        """Execute the push operation with retry.

        Args:
            task: PushTask instance
            skill_zip: Path to skill ZIP file

        Returns:
            Result dict
        """
        max_retries = task.max_retries

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Push attempt {attempt + 1}/{max_retries} for {task.skill_name}-{task.version}",
                    extra={
                        "task_id": task.id,
                        "skill_name": task.skill_name,
                        "version": task.version,
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    }
                )

                # Clone or pull repository
                repo_path = self.client.clone_or_pull_repo()

                # Extract skill to versioned folder
                folder = self.client.add_skill_folder(
                    repo_path,
                    skill_zip,
                    task.skill_name,
                    task.version
                )

                # Commit and push
                start_time = time.time()
                commit_hash = self.client.commit_and_push(
                    repo_path,
                    f"feat: add {task.skill_name}-{task.version}"
                )
                push_duration = time.time() - start_time

                logger.info(
                    f"Successfully pushed {task.skill_name}-{task.version} at {commit_hash[:8]}",
                    extra={
                        "task_id": task.id,
                        "commit_hash": commit_hash,
                        "duration_seconds": push_duration,
                        "folder": folder
                    }
                )

                # Update metrics
                self.metrics["total_push_time_seconds"] += push_duration

                return {
                    "success": True,
                    "commit_hash": commit_hash,
                    "folder": folder,
                    "duration": push_duration
                }

            except (GiteaError, NetworkError) as e:
                # Determine if error is retryable
                is_retryable = isinstance(e, NetworkError)

                if not is_retryable or attempt >= max_retries - 1:
                    # Fatal error or max retries reached
                    logger.error(
                        f"Push failed for {task.skill_name}-{task.version}: {e}",
                        extra={"task_id": task.id, "fatal": not is_retryable},
                        exc_info=True
                    )
                    return {"success": False, "error": str(e), "fatal": not is_retryable}

                # Calculate retry delay with exponential backoff
                retry_delay = min(
                    self.retry_base_delay * (2 ** attempt),
                    self.retry_max_delay
                )

                logger.warning(
                    f"Push failed for {task.skill_name}-{task.version}, "
                    f"retrying in {retry_delay}s: {e}",
                    extra={
                        "task_id": task.id,
                        "retry_count": attempt + 1,
                        "next_retry_in": retry_delay
                    }
                )

                await asyncio.sleep(retry_delay)

        # All retries exhausted
        return {
            "success": False,
            "error": "Max retries exhausted",
            "fatal": False
        }

    async def _timeout_monitor(self, task: PushTask, timeout_seconds: int):
        """Monitor task for timeout.

        Args:
            task: PushTask instance
            timeout_seconds: Timeout in seconds
        """
        try:
            await asyncio.sleep(timeout_seconds)
            logger.warning(
                f"Task {task.id} ({task.skill_name}-{task.version}) timeout after {timeout_seconds}s",
                extra={"task_id": task.id, "timeout_seconds": timeout_seconds}
            )
        except asyncio.CancelledError:
            # Task completed, cancel timeout monitor
            pass

    async def _handle_success(self, task_id: int, result: Dict):
        """Handle successful push.

        Args:
            task_id: Task ID
            result: Result dict from push operation
        """
        update_push_status(
            task_id,
            "success",
            commit_hash=result["commit_hash"],
            gitea_path=result["folder"]
        )

        self.metrics["tasks_succeeded"] += 1

        # Send success notification (if configured)
        await self._send_notification(
            task_id=task_id,
            status="success",
            details=result
        )

    async def _handle_failure(self, task: PushTask, result: Dict):
        """Handle failed push with retry logic.

        Args:
            task: PushTask instance
            result: Result dict from push operation
        """
        task_id = task.id
        is_fatal = result.get("fatal", False)
        is_timeout = result.get("timeout", False)

        if is_fatal or is_timeout:
            # Don't retry fatal errors or timeouts
            update_push_status(
                task_id,
                "failed",
                retry_count=task.retry_count + 1,
                error_message=result["error"]
            )
            self.metrics["tasks_failed"] += 1

        elif task.can_retry:
            # Re-queue for retry
            new_retry_count = task.retry_count + 1
            update_push_status(
                task_id,
                "pending",
                retry_count=new_retry_count,
                error_message=result["error"]
            )

            self.metrics["tasks_retried"] += 1

            logger.info(
                f"Task {task_id} re-queued for retry ({new_retry_count}/{task.max_retries})",
                extra={"task_id": task_id, "retry_count": new_retry_count}
            )
        else:
            # Max retries reached
            update_push_status(
                task_id,
                "failed",
                retry_count=task.retry_count + 1,
                error_message=result["error"]
            )
            self.metrics["tasks_failed"] += 1

        # Send failure notification for critical failures
        if is_fatal or not task.can_retry:
            await self._send_notification(
                task_id=task_id,
                status="failed",
                details=result
            )

    async def _send_notification(self, task_id: int, status: str, details: Dict):
        """Send push status notification (optional).

        Can be extended to send:
        - Email notifications
        - Webhook callbacks
        - Slack/Discord messages

        Args:
            task_id: Task ID
            status: Task status
            details: Result details
        """
        # Get task details for notification
        try:
            with get_connection() as conn:
                task_data = conn.execute("""
                    SELECT t.*, s.skill_name, s.version, u.employee_id as uploader
                    FROM gitea_push_tasks t
                    JOIN skills s ON t.skill_id = s.id
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE t.id = %s
                """, (task_id,)).fetchone()

                if task_data:
                    logger.info(
                        f"Push notification: {status}",
                        extra={
                            "notification_type": "gitea_push",
                            "status": status,
                            "task_id": task_id,
                            "skill_name": task_data["skill_name"],
                            "version": task_data["version"],
                            "uploader": task_data["uploader"]
                        }
                    )

                    # TODO: Add webhook/email notification here
                    # Example: send_webhook(task_data, status, details)

        except Exception as e:
            logger.error(f"Failed to send notification for task {task_id}: {e}")

    async def _health_check(self):
        """Perform health check and log metrics."""
        try:
            self.metrics["last_health_check"] = datetime.utcnow().isoformat()

            # Calculate success rate
            total = self.metrics["tasks_processed"]
            succeeded = self.metrics["tasks_succeeded"]
            success_rate = (succeeded / total * 100) if total > 0 else 0

            # Calculate average push time
            avg_push_time = (
                self.metrics["total_push_time_seconds"] / succeeded
                if succeeded > 0 else 0
            )

            # Get queue statistics
            with get_connection() as conn:
                queue_stats = conn.execute("""
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM gitea_push_tasks
                    WHERE created_at >= datetime('now', '-1 hour')
                    GROUP BY status
                """).fetchall()

            logger.info(
                f"Health check: success_rate={success_rate:.1f}%, "
                f"processed={total}, avg_push_time={avg_push_time:.1f}s",
                extra={
                    "health_check": True,
                    "metrics": self.metrics,
                    "success_rate": round(success_rate, 2),
                    "avg_push_time_seconds": round(avg_push_time, 2),
                    "queue_stats": dict(queue_stats) if queue_stats else {}
                }
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)

    async def run(self):
        """Main service loop with health monitoring."""
        self.running = True
        self.metrics["service_start_time"] = datetime.utcnow().isoformat()

        logger.info(
            f"Gitea push service v2 started (interval={self.interval}s, "
            f"max_concurrent={self.max_concurrent_tasks})",
            extra={
                "service": "gitea_push_v2",
                "interval": self.interval,
                "max_concurrent_tasks": self.max_concurrent_tasks,
                "retry_base_delay": self.retry_base_delay
            }
        )

        last_health_check = time.time()

        while self.running:
            try:
                # Periodic health check
                if time.time() - last_health_check >= self.health_check_interval:
                    await self._health_check()
                    last_health_check = time.time()

                # Get pending tasks ordered by priority and creation time
                tasks = await self._get_pending_tasks()

                if tasks:
                    logger.info(
                        f"Processing {len(tasks)} pending tasks",
                        extra={"task_count": len(tasks)}
                    )

                    # Process tasks concurrently (up to semaphore limit)
                    process_coroutines = [self.process_task(task) for task in tasks]
                    await asyncio.gather(*process_coroutines, return_exceptions=True)

                # Wait before next scan
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.error(f"Service loop error: {e}", exc_info=True)
                await asyncio.sleep(self.interval)

    async def _get_pending_tasks(self) -> List[PushTask]:
        """Get pending tasks from database with priority ordering.

        Returns:
            List of PushTask instances
        """
        try:
            rows = get_pending_tasks(limit=10)

            tasks = []
            for row in rows:
                # Determine priority based on age and retry count
                age = row.get('age_seconds', 0)
                retry_count = row.get('retry_count', 0)

                # Older tasks and retried tasks get higher priority
                if retry_count > 0 or age > 300:  # 5 minutes
                    priority = TaskPriority.HIGH
                else:
                    priority = TaskPriority.NORMAL

                task = PushTask(
                    id=row['id'],
                    skill_id=row['skill_id'],
                    skill_name=row['skill_name'],
                    version=row['version'],
                    filename=row['filename'],
                    priority=priority,
                    max_retries=row.get('max_retries', 3),
                    retry_count=retry_count,
                    created_at=datetime.fromisoformat(row['created_at']) if isinstance(row.get('created_at'), str) else None
                )
                tasks.append(task)

            # Sort by priority (high first) and age (old first)
            tasks.sort(key=lambda t: (-t.priority.value, -t.age_seconds))

            return tasks

        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}", exc_info=True)
            return []

    def stop(self):
        """Stop the service gracefully."""
        self.running = False

        logger.info(
            "Gitea push service stopping",
            extra={
                "service": "gitea_push_v2",
                "final_metrics": self.metrics
            }
        )
