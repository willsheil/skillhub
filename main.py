#!/usr/bin/env python3
"""
Claude Code Skill Registry - Private Marketplace Server

Main entry point for the FastAPI application.
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import os
import uvicorn


def main():
    """Run the FastAPI application using uvicorn."""
    # Import create_app after loading environment variables
    from core.app import create_app

    # Create the FastAPI application
    app = create_app(
        title="Skill Registry",
        version="1.0.0",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_dir="./logs",
        enable_json_log=True,
        enable_console_log=True,
    )

    # Get host and port from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "28000"))

    # Run the application
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "INFO").lower(),
    )


if __name__ == "__main__":
    main()
