"""
Health check routes - Service health monitoring.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from pathlib import Path

from core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring services.

    Returns:
        Service status information including:
        - status: "healthy" or "unhealthy"
        - timestamp: Current server time
        - version: API version
        - uptime: Service uptime (if available)
    """
    settings = get_settings()
    
    # Basic health checks
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "Skill Registry"
    }

    # Check if plugins directory is accessible
    try:
        if not settings.PLUGINS_DIR.exists():
            health_status["status"] = "unhealthy"
            health_status["error"] = "Plugins directory not accessible"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    # Return appropriate status code
    if health_status["status"] == "healthy":
        return health_status
    else:
        raise HTTPException(status_code=503, detail=health_status)
