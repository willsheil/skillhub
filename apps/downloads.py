"""Download routes."""

from fastapi import APIRouter, Request, Depends

router = APIRouter()


@router.get("/api/user/downloads")
async def get_user_downloads(request: Request):
    """Get user's download history."""
    from main import get_current_user
    from db.repositories import DownloadRepository

    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid session")

    downloads = DownloadRepository.get_by_user(user_id)
    return {
        "items": [d.to_dict() for d in downloads],
        "pagination": {"page": 1, "page_size": 20, "total": len(downloads)}
    }


@router.get("/api/batch-download")
async def batch_download(request: Request, skills: str = None):
    """Batch download skills."""
    from fastapi.responses import StreamingResponse
    import io
    import zipfile
    import os

    if not skills:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No skills specified")

    skill_names = skills.split(",")
    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        plugins_dir = os.path.join(base_dir, "plugins")

        for skill_name in skill_names:
            skill_name = skill_name.strip()
            # Find the skill in any source directory
            for source in ["opensource", "icsl", "huawei"]:
                skill_path = os.path.join(plugins_dir, source, skill_name)
                if os.path.exists(skill_path):
                    # Add all files in the skill directory
                    for root, dirs, files in os.walk(skill_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(skill_name, os.path.relpath(file_path, skill_path))
                            zf.write(file_path, arcname)
                    break

    memory_file.seek(0)

    return StreamingResponse(
        iter([memory_file.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=skills.zip"}
    )
