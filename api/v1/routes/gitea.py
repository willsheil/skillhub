"""
Gitea integration routes - Push status, task management.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from db.repositories import GiteaTaskRepository, SkillRepository
from api.v1.dependencies import get_current_user, require_admin

router = APIRouter()


@router.get("/status")
async def get_gitea_status(current_user: dict = Depends(get_current_user)):
    """Get Gitea push service status."""
    stats = GiteaTaskRepository.get_stats()

    from core.config import get_settings
    settings = get_settings()

    return {
        "enabled": settings.is_gitea_enabled,
        "repo_url": settings.GITEA_REPO_URL,
        "task_stats": stats,
    }


@router.get("/tasks")
async def list_gitea_tasks(
    status: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(require_admin)
):
    """List Gitea push tasks (admin only)."""
    if status:
        # Filter by status - need to implement in repo
        tasks = GiteaTaskRepository.get_pending(limit=limit)
    else:
        tasks = GiteaTaskRepository.get_pending(limit=limit)

    return {
        "items": [t.to_dict() for t in tasks],
    }


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: int,
    current_user: dict = Depends(require_admin)
):
    """Retry a failed push task (admin only)."""
    task = GiteaTaskRepository.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "failed":
        raise HTTPException(status_code=400, detail="Task is not in failed state")

    GiteaTaskRepository.mark_retry_pending(task_id)

    return {"success": True, "message": "Task queued for retry"}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific task."""
    task = GiteaTaskRepository.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get associated skill info
    skill = SkillRepository.get_by_id(task.skill_id)

    return {
        "task": task.to_dict(),
        "skill": skill.to_dict() if skill else None,
    }
