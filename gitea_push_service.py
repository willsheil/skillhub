import asyncio
import logging
from pathlib import Path
from gitea_client import GiteaClient
from gitea_integration import get_pending_tasks, update_push_status
from database import get_connection

logger = logging.getLogger(__name__)

class GiteaPushService:
    """Background service to process Gitea push tasks."""

    def __init__(self, interval: int = 30):
        """Initialize push service.

        Args:
            interval: Scan interval in seconds (default: 30)
        """
        self.client = GiteaClient()
        self.interval = interval
        self.running = False

    async def process_task(self, task: dict):
        """Process a single push task.

        Args:
            task: Task dictionary from database
        """
        task_id = task['id']
        skill_zip = Path("./plugins") / task['filename']

        if not skill_zip.exists():
            error = f"Skill ZIP not found: {skill_zip}"
            update_push_status(task_id, "failed", error_message=error)
            logger.error(f"Task {task_id} failed: {error}")
            return

        # Update status to pushing
        update_push_status(task_id, "pushing")

        try:
            # Execute push with retry
            result = self.client.push_with_retry(
                skill_zip,
                task['skill_name'],
                task['version'],
                max_retries=task['max_retries']
            )

            if result['success']:
                # Push succeeded
                update_push_status(
                    task_id,
                    "success",
                    commit_hash=result['commit_hash'],
                    gitea_path=result['folder']
                )
                logger.info(f"Task {task_id} succeeded: {result['commit_hash'][:8]}")
            else:
                # Push failed
                retry_count = task['retry_count'] + 1
                if retry_count < task['max_retries']:
                    # Re-queue for retry
                    update_push_status(
                        task_id,
                        "pending",
                        retry_count=retry_count,
                        error_message=result['error']
                    )
                    logger.warning(f"Task {task_id} will retry ({retry_count}/{task['max_retries']})")
                else:
                    # Max retries exceeded
                    update_push_status(
                        task_id,
                        "failed",
                        retry_count=retry_count,
                        error_message=result['error']
                    )
                    logger.error(f"Task {task_id} failed permanently: {result['error']}")

        except Exception as e:
            # Unexpected error
            logger.exception(f"Unexpected error processing task {task_id}")
            update_push_status(
                task_id,
                "failed",
                error_message=f"Unexpected error: {str(e)}"
            )

    async def run(self):
        """Main service loop."""
        self.running = True
        logger.info("Gitea push service started")

        while self.running:
            try:
                # Get pending tasks
                tasks = get_pending_tasks(limit=5)

                if tasks:
                    logger.info(f"Processing {len(tasks)} pending tasks")

                    # Process each task sequentially
                    for task in tasks:
                        await self.process_task(task)

                # Wait before next scan
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.error(f"Service error: {e}")
                await asyncio.sleep(self.interval)

    def stop(self):
        """Stop the service."""
        self.running = False
        logger.info("Gitea push service stopped")
