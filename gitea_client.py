"""
GiteaClient - Git operations wrapper for Gitea repository integration.

This module provides a client for interacting with Gitea repositories,
handling Git operations like clone, pull, commit, and push with proper
error handling and retry logic.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class GiteaError(Exception):
    """Base exception class for Gitea operation errors."""
    pass


class AuthenticationError(GiteaError):
    """Authentication failed - fatal error.

    Raised when Git authentication fails due to invalid credentials
    or missing permissions. This is a fatal error that requires
    configuration fix before retry.
    """
    pass


class RepositoryNotFoundError(GiteaError):
    """Repository not found - fatal error.

    Raised when the specified repository does not exist or is
    inaccessible. This is a fatal error that requires configuration
    fix before retry.
    """
    pass


class NetworkError(GiteaError):
    """Network error - retryable.

    Raised when network operations fail due to connectivity issues,
    timeouts, or temporary server problems. These errors are
    retryable.
    """
    pass


class GitConflictError(GiteaError):
    """Git conflict - needs manual handling.

    Raised when Git operations fail due to conflicts, merge issues,
    or other Git state problems that may require manual intervention.
    """
    pass


class GiteaClient:
    """Client for interacting with Gitea repositories via Git operations."""

    def __init__(self):
        """Initialize GiteaClient from environment variables.

        Environment Variables:
            GITEA_REPO_URL: URL of the Gitea repository (required)
            GITEA_TOKEN: Personal access token for authentication (optional)

        Raises:
            ValueError: If GITEA_REPO_URL is not set
        """
        self.repo_url = os.getenv("GITEA_REPO_URL")
        self.token = os.getenv("GITEA_TOKEN")

        if not self.repo_url:
            raise ValueError("GITEA_REPO_URL environment variable not set")

        # Create temp directory for git operations
        self.temp_dir = Path(tempfile.gettempdir()) / "gitea_sync"
        self.temp_dir.mkdir(exist_ok=True)

        logger.info(f"GiteaClient initialized with repo: {self.repo_url}")

    def _run_git_command(self, cwd: Path, args: list) -> Tuple[str, str, int]:
        """Run git command and return stdout, stderr, returncode.

        Args:
            cwd: Working directory for command execution
            args: List of command arguments (without 'git' prefix)

        Returns:
            Tuple of (stdout, stderr, returncode)

        Raises:
            subprocess.TimeoutExpired: If command times out
        """
        cmd = ["git"] + args
        logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        return result.stdout, result.stderr, result.returncode
