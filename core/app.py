"""
FastAPI app factory for SkillHub application.

Provides create_app() function to initialize and configure the FastAPI application.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import init_db
from logging_config import setup_logging
from core.middleware import SessionMiddleware, CORSMiddleware


logger = logging.getLogger("skillhub")


# Configuration
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

PENDING_DIR = Path("./data/pending")
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Session secret key
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    Initializes database on startup and handles cleanup on shutdown.
    """
    # Startup
    init_db()
    logger.info("Database initialized")

    # Start Gitea push service if configured
    if os.getenv("GITEA_REPO_URL"):
        try:
            import asyncio
            from gitea_push_service import GiteaPushService

            push_service = GiteaPushService(
                interval=int(os.getenv("GITEA_PUSH_INTERVAL", "30"))
            )

            # Start service in background
            asyncio.create_task(push_service.run())

            logger.info("Gitea push service started")
        except Exception as e:
            logger.error(f"Failed to start Gitea push service: {e}")
    else:
        logger.info("Gitea integration disabled (GITEA_REPO_URL not set)")

    yield

    # Shutdown
    logger.info("Shutting down...")


def create_app(
    title: str = "Skill Registry",
    version: str = "1.0.0",
    log_level: str = None,
    log_dir: str = "./logs",
    enable_json_log: bool = True,
    enable_console_log: bool = True,
) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        title: Application title
        version: Application version
        log_level: Logging level (from env if not specified)
        log_dir: Directory for log files
        enable_json_log: Enable JSON structured logging
        enable_console_log: Enable console output

    Returns:
        Configured FastAPI application instance
    """
    # Setup logging
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(
        level=log_level,
        log_dir=log_dir,
        enable_json=enable_json_log,
        enable_console=enable_console_log
    )

    # Create FastAPI app
    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan
    )

    # Add middleware
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
    app.add_middleware(CORSMiddleware)

    # Static files and templates
    app.mount("/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="templates")
    app.state.templates = templates
    app.state.plugins_dir = PLUGINS_DIR
    app.state.pending_dir = PENDING_DIR

    logger.info(f"FastAPI app created: {title} v{version}")

    return app
