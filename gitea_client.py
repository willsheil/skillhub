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
from typing import Optional, Tuple, Dict
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

        # Git configuration for commits
        self.git_user_name = os.getenv("GIT_USER_NAME", "Skill Registry")
        self.git_user_email = os.getenv("GIT_USER_EMAIL", "registry@local")

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

        # Set environment to disable proxy for localhost
        env = os.environ.copy()
        no_proxy = os.getenv("NO_PROXY", "127.0.0.1,localhost")
        env["NO_PROXY"] = no_proxy
        env["no_proxy"] = no_proxy
        # Also explicitly unset http/https proxy for localhost
        env["HTTP_PROXY"] = ""
        env["HTTPS_PROXY"] = ""
        env["http_proxy"] = ""
        env["https_proxy"] = ""

        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )

        return result.stdout, result.stderr, result.returncode

    def _ensure_git_config(self, repo_path: Path):
        """Ensure git config is set for the repository.

        Args:
            repo_path: Path to git repository
        """
        # Set user name and email for this repository
        self._run_git_command(
            repo_path,
            ["config", "user.name", self.git_user_name]
        )
        self._run_git_command(
            repo_path,
            ["config", "user.email", self.git_user_email]
        )

    def _get_default_branch(self, repo_path: Path) -> str:
        """Get the default branch name of the remote repository.

        Args:
            repo_path: Path to git repository

        Returns:
            Default branch name (usually 'main' or 'master')
        """
        # Try to get the default branch from remote
        stdout, stderr, returncode = self._run_git_command(
            repo_path,
            ["symbolic-ref", "refs/remotes/origin/HEAD"]
        )

        if returncode == 0 and stdout:
            # Format: refs/remotes/origin/main
            branch = stdout.strip().split('/')[-1]
            logger.info(f"Detected default branch: {branch}")
            return branch

        # Fallback: try common branch names
        for branch in ['main', 'master']:
            stdout, stderr, returncode = self._run_git_command(
                repo_path,
                ["ls-remote", "--symref", "--exit-code", "origin", "HEAD"]
            )
            if returncode == 0 and branch in stdout:
                logger.info(f"Detected default branch from ls-remote: {branch}")
                return branch

        # Default to 'main' for new repositories
        logger.info("Could not detect default branch, using 'main'")
        return 'main'

    def clone_or_pull_repo(self) -> Path:
        """Clone or pull latest code from Gitea repository.

        Returns:
            Path to local repository
        """
        local_path = self.temp_dir / "repo"

        if local_path.exists():
            logger.info(f"Repository exists, pulling latest: {local_path}")
            # Ensure git config is set
            self._ensure_git_config(local_path)
            # Get default branch and pull
            branch = self._get_default_branch(local_path)
            self._git_pull(local_path, branch)
        else:
            logger.info(f"Cloning repository: {self.repo_url}")
            self._git_clone(self.repo_url, local_path)
            # Ensure git config is set after clone
            self._ensure_git_config(local_path)

        return local_path

    def _git_clone(self, url: str, path: Path):
        """Clone repository.

        Args:
            url: Repository URL
            path: Local path to clone to

        Raises:
            AuthenticationError: If authentication fails
            RepositoryNotFoundError: If repository doesn't exist
            GiteaError: For other clone failures
        """
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
            error_msg = stderr.strip()
            if "Authentication failed" in error_msg or "could not read Username" in error_msg:
                raise AuthenticationError(f"Git authentication failed: {error_msg}")
            elif "repository not found" in error_msg.lower() or "could not find repository" in error_msg.lower():
                raise RepositoryNotFoundError(f"Repository not found: {url}")
            # Empty repository is ok - will be initialized on first push
            elif "could not find remote ref" in error_msg or "does not appear to be a git repository" in error_msg:
                logger.warning(f"Repository appears to be empty: {error_msg}")
                # Create an empty repo structure
                path.mkdir(parents=True, exist_ok=True)
                self._run_git_command(path, ["init"])
                self._run_git_command(path, ["remote", "add", "origin", url])
                self._ensure_git_config(path)
            else:
                raise GiteaError(f"Git clone failed: {error_msg}")

    def _git_pull(self, path: Path, branch: str = None):
        """Pull latest changes.

        Args:
            path: Path to git repository
            branch: Branch name to pull (default: auto-detect)
        """
        if branch is None:
            branch = self._get_default_branch(path)

        stdout, stderr, returncode = self._run_git_command(
            path,
            ["pull", "origin", branch]
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
        # Ensure git config is set
        self._ensure_git_config(repo_path)

        # Get the current branch (or use 'main' as default for empty repos)
        try:
            branch = self._get_default_branch(repo_path)
        except Exception:
            branch = 'main'
            # Set the branch for empty repo
            self._run_git_command(repo_path, ["checkout", "-b", branch])

        # Stage all changes
        self._git_add_all(repo_path)

        # Create commit and get hash
        commit_hash = self._git_commit(repo_path, message)

        # Push to remote with -u for first push
        try:
            stdout, stderr, returncode = self._run_git_command(
                repo_path,
                ["push", "-u", "origin", branch]
            )

            if returncode != 0:
                if "Authentication failed" in stderr:
                    raise AuthenticationError(f"Git push authentication failed: {stderr}")
                elif "network" in stderr.lower() or "timeout" in stderr.lower():
                    raise NetworkError(f"Git push network error: {stderr}")
                else:
                    raise GiteaError(f"Git push failed: {stderr}")

        except GiteaError as e:
            # Try regular push if -u flag fails
            logger.warning(f"Push with -u failed, trying regular push: {e}")
            self._git_push(repo_path, branch)

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

    def _git_push(self, path: Path, branch: str = None):
        """Push commits to remote repository.

        Args:
            path: Path to git repository
            branch: Branch name to push to (default: auto-detect)

        Raises:
            AuthenticationError: If authentication fails
            NetworkError: If network or timeout errors occur
            GiteaError: For other failures
        """
        if branch is None:
            branch = self._get_default_branch(path)

        stdout, stderr, returncode = self._run_git_command(
            path,
            ["push", "origin", branch]
        )

        if returncode != 0:
            if "Authentication failed" in stderr:
                raise AuthenticationError(f"Git push authentication failed: {stderr}")
            elif "network" in stderr.lower() or "timeout" in stderr.lower():
                raise NetworkError(f"Git push network error: {stderr}")
            else:
                raise GiteaError(f"Git push failed: {stderr}")

    def push_with_retry(self, skill_zip: Path, skill_name: str,
                       version: str, max_retries: int = 3) -> Dict:
        """Push skill to Gitea with retry logic.

        Args:
            skill_zip: Path to skill ZIP file
            skill_name: Name of the skill
            version: Version string
            max_retries: Maximum number of retry attempts

        Returns:
            Dict with success status, commit_hash, folder, or error
        """
        import time

        last_error = None
        retry_intervals = [1, 5, 30]  # seconds

        for attempt in range(max_retries):
            try:
                logger.info(f"Push attempt {attempt + 1}/{max_retries} for {skill_name}-{version}")

                # Clone or pull repository
                repo_path = self.clone_or_pull_repo()

                # Extract skill to versioned folder
                folder = self.add_skill_folder(
                    repo_path,
                    skill_zip,
                    skill_name,
                    version
                )

                # Commit and push
                commit_hash = self.commit_and_push(
                    repo_path,
                    f"feat: add {skill_name}-{version}"
                )

                logger.info(f"Successfully pushed {skill_name}-{version} at {commit_hash[:8]}")

                return {
                    "success": True,
                    "commit_hash": commit_hash,
                    "folder": folder
                }

            except (AuthenticationError, RepositoryNotFoundError, GitConflictError) as e:
                # Fatal errors - don't retry
                logger.error(f"Fatal error pushing {skill_name}-{version}: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "fatal": True
                }

            except NetworkError as e:
                # Retryable error
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = retry_intervals[min(attempt, len(retry_intervals) - 1)]
                    logger.warning(f"Network error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} attempts: {e}")

            except Exception as e:
                # Unknown error
                last_error = e
                logger.error(f"Unexpected error: {e}")
                break

        # All retries failed
        return {
            "success": False,
            "error": str(last_error),
            "fatal": False
        }
