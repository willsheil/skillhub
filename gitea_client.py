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

    def clone_or_pull_repo(self) -> Path:
        """Clone or pull latest code from Gitea repository.

        Returns:
            Path to local repository
        """
        local_path = self.temp_dir / "repo"

        if local_path.exists():
            logger.info(f"Repository exists, pulling latest: {local_path}")
            self._git_pull(local_path)
        else:
            logger.info(f"Cloning repository: {self.repo_url}")
            self._git_clone(self.repo_url, local_path)

        return local_path

    def _git_clone(self, url: str, path: Path):
        """Clone repository."""
        # Inject token into URL for authentication
        if self.token:
            # URL format: https://token@url
            from urllib.parse import urlparse
            parsed = urlparse(url)
            auth_url = f"{parsed.scheme}://{self.token}@{parsed.netloc}{parsed.path}"
            if parsed.query:
                auth_url += f"?{parsed.query}"
        else:
            auth_url = url

        stdout, stderr, returncode = self._run_git_command(
            Path.cwd(),
            ["clone", auth_url, str(path)]
        )

        if returncode != 0:
            if "Authentication failed" in stderr or "could not read Username" in stderr:
                raise AuthenticationError(f"Git authentication failed: {stderr}")
            elif "repository not found" in stderr.lower() or "could not find repository" in stderr.lower():
                raise RepositoryNotFoundError(f"Repository not found: {url}")
            else:
                raise GiteaError(f"Git clone failed: {stderr}")

    def _git_pull(self, path: Path):
        """Pull latest changes."""
        stdout, stderr, returncode = self._run_git_command(
            path,
            ["pull", "origin", "master"]
        )

        if returncode != 0:
            if "Authentication failed" in stderr:
                raise AuthenticationError(f"Git authentication failed: {stderr}")
            else:
                raise NetworkError(f"Git pull failed: {stderr}")

    def add_skill_folder(self, repo_path: Path, skill_zip: Path,
                        skill_name: str, version: str) -> str:
        """Extract skill ZIP to target folder in repository.

        Args:
            repo_path: Path to local git repository
            skill_zip: Path to skill ZIP file
            skill_name: Name of the skill
            version: Version string

        Returns:
            Folder name created (format: {skill_name}-{version})
        """
        import shutil
        import zipfile

        folder_name = f"{skill_name}-{version}"
        target_path = repo_path / folder_name

        # Remove old version if exists
        if target_path.exists():
            logger.info(f"Removing old version: {folder_name}")
            shutil.rmtree(target_path)

        # Extract ZIP to target location
        logger.info(f"Extracting skill to: {folder_name}")
        with zipfile.ZipFile(skill_zip, 'r') as zf:
            zf.extractall(target_path)

        # Verify extraction
        if not target_path.exists():
            raise GiteaError(f"Failed to extract skill ZIP to {target_path}")

        return folder_name

    def commit_and_push(self, repo_path: Path, message: str) -> str:
        """Commit and push changes to remote repository.

        Args:
            repo_path: Path to local git repository
            message: Commit message

        Returns:
            Commit hash (40-character SHA-1)

        Raises:
            GiteaError: If add, commit, or push operations fail
        """
        # Stage all changes
        self._git_add_all(repo_path)

        # Create commit and get hash
        commit_hash = self._git_commit(repo_path, message)

        # Push to remote
        self._git_push(repo_path)

        return commit_hash

    def _git_add_all(self, path: Path):
        """Stage all changes for commit.

        Args:
            path: Path to git repository

        Raises:
            GiteaError: If git add fails
        """
        stdout, stderr, returncode = self._run_git_command(
            path,
            ["add", "-A"]
        )

        if returncode != 0:
            raise GiteaError(f"Git add failed: {stderr}")

    def _git_commit(self, path: Path, message: str) -> str:
        """Create commit and return commit hash.

        Args:
            path: Path to git repository
            message: Commit message

        Returns:
            Commit hash (40-character SHA-1)

        Raises:
            GitConflictError: If commit fails due to conflicts
            GiteaError: If commit fails and hash cannot be retrieved
        """
        import re

        stdout, stderr, returncode = self._run_git_command(
            path,
            ["commit", "-m", message]
        )

        if returncode != 0:
            raise GitConflictError(f"Git commit failed: {stderr}")

        # Extract commit hash from stdout
        # Format: [master abc123...] message
        hash_match = re.search(r'\b([a-f0-9]{40})\b', stdout)

        if hash_match:
            return hash_match.group(1)

        # Fallback: get hash from git log
        stdout, stderr, returncode = self._run_git_command(
            path,
            ["log", "-1", "--format=%H"]
        )

        if returncode == 0 and stdout.strip():
            return stdout.strip()

        raise GiteaError("Git commit succeeded but could not retrieve commit hash")

    def _git_push(self, path: Path):
        """Push commits to remote repository.

        Args:
            path: Path to git repository

        Raises:
            AuthenticationError: If authentication fails
            NetworkError: If network or timeout errors occur
            GiteaError: For other failures
        """
        stdout, stderr, returncode = self._run_git_command(
            path,
            ["push", "origin", "master"]
        )

        if returncode != 0:
            if "Authentication failed" in stderr:
                raise AuthenticationError(f"Git push authentication failed: {stderr}")
            elif "network" in stderr.lower() or "timeout" in stderr.lower():
                raise NetworkError(f"Git push network error: {stderr}")
            else:
                raise GiteaError(f"Git push failed: {stderr}")
