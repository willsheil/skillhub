import asyncio
import logging
from pathlib import Path
from .gitea_client import GiteaClient
from .gitea_integration import get_pending_tasks, update_push_status
from db.connection import get_connection

logger = logging.getLogger(__name__)

# Sync wrapper for APScheduler
def run_push_task():
    """Synchronous wrapper for APScheduler to run async process_once."""
    asyncio.run(process_push_tasks_once())


async def process_push_tasks_once():
    """Process pending tasks once (async version)."""
    try:
        logger.info("Processing pending Gitea push tasks...")
        tasks = get_pending_tasks(limit=5)

        if tasks:
            logger.info(f"Found {len(tasks)} pending tasks")
            client = GiteaClient()
            for task in tasks:
                await process_task_sync(client, task)
        else:
            logger.info("No pending tasks to process")
    except Exception as e:
        logger.error(f"Error in process_push_tasks_once: {e}")


async def process_task_sync(client: GiteaClient, task: dict):
    """Process a single push task (async version)."""
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
        # Get skill_name and version from task
        skill_name = task.get('skill_name', task['filename'].replace('.zip', '').rsplit('-', 1)[0])
        version = task.get('version', '1.0.0')

        # Push to Gitea using push_with_retry
        result = client.push_with_retry(
            skill_zip,
            skill_name,
            version,
            max_retries=3
        )

        if result['success']:
            # Update status to success
            update_push_status(
                task_id,
                "success",
                commit_hash=result['commit_hash'],
                gitea_path=result.get('folder', f'skills/{skill_name}')
            )
            logger.info(f"Task {task_id} completed successfully")
        else:
            # Push failed
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Task {task_id} failed: {error_msg}")
            update_push_status(task_id, "failed", error_message=error_msg)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Task {task_id} failed: {error_msg}")
        update_push_status(task_id, "failed", error_message=error_msg)


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

    async def process_once(self):
        """Process pending tasks once (for scheduled task)."""
        try:
            logger.info("Processing pending Gitea push tasks...")
            tasks = get_pending_tasks(limit=5)

            if tasks:
                logger.info(f"Found {len(tasks)} pending tasks")
                for task in tasks:
                    await self.process_task(task)
            else:
                logger.info("No pending tasks to process")
        except Exception as e:
            logger.error(f"Error in process_once: {e}")

    def stop(self):
        """Stop the service."""
        self.running = False
        logger.info("Gitea push service stopped")
