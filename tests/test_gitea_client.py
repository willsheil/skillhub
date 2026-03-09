"""
Tests for GiteaClient module.

Tests cover:
- Client initialization with environment variables
- Exception hierarchy
- Basic configuration validation
- Git user configuration
- Default branch detection
- Empty repository handling
"""

import os
import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitea_client import GiteaClient, GiteaError, AuthenticationError, RepositoryNotFoundError, NetworkError, GitConflictError


def test_gitea_client_initialization(monkeypatch):
    """Test GiteaClient initialization with valid environment variables."""
    # Mock environment variables
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token_123")

    client = GiteaClient()

    assert client.repo_url == "https://localhost:3000/test/repo.git"
    assert client.token == "test_token_123"
    assert client.temp_base.exists()
    assert client.temp_base.name == "gitea_sync"
    # New: check git config attributes
    assert client.git_user_name == "Skill Registry"
    assert client.git_user_email == "registry@local"


def test_gitea_client_initialization_with_custom_git_config(monkeypatch):
    """Test GiteaClient initialization with custom git config from environment."""
    # Mock environment variables with custom git config
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token_123")
    monkeypatch.setenv("GIT_USER_NAME", "Custom User")
    monkeypatch.setenv("GIT_USER_EMAIL", "custom@example.com")

    client = GiteaClient()

    assert client.git_user_name == "Custom User"
    assert client.git_user_email == "custom@example.com"


def test_gitea_client_missing_repo_url(monkeypatch):
    """Test that GiteaClient raises ValueError when GITEA_REPO_URL is not set."""
    # Remove GITEA_REPO_URL
    monkeypatch.delenv("GITEA_REPO_URL", raising=False)

    with pytest.raises(ValueError) as exc_info:
        GiteaClient()

    assert "GITEA_REPO_URL environment variable not set" in str(exc_info.value)


def test_gitea_client_temp_dir_creation(monkeypatch, tmp_path):
    """Test that GiteaClient creates temp_dir if it doesn't exist."""
    # Mock environment variables with a custom temp path
    custom_temp = tmp_path / "custom_gitea_sync"
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")
    monkeypatch.setenv("TEMP", str(tmp_path))

    # Ensure directory doesn't exist
    if custom_temp.exists():
        custom_temp.rmdir()

    client = GiteaClient()

    # Temp dir should be created
    assert client.temp_base.exists()


def test_exception_hierarchy():
    """Test that all exception classes inherit from GiteaError."""
    assert issubclass(AuthenticationError, GiteaError)
    assert issubclass(RepositoryNotFoundError, GiteaError)
    assert issubclass(NetworkError, GiteaError)
    assert issubclass(GitConflictError, GiteaError)


def test_exception_instantiation():
    """Test that exception classes can be instantiated with messages."""
    error_msg = "Test error message"

    base_error = GiteaError(error_msg)
    auth_error = AuthenticationError(error_msg)
    repo_error = RepositoryNotFoundError(error_msg)
    network_error = NetworkError(error_msg)
    conflict_error = GitConflictError(error_msg)

    assert str(base_error) == error_msg
    assert str(auth_error) == error_msg
    assert str(repo_error) == error_msg
    assert str(network_error) == error_msg
    assert str(conflict_error) == error_msg


def test_exception_catching():
    """Test that specific exceptions can be caught as base GiteaError."""
    try:
        raise AuthenticationError("Auth failed")
    except GiteaError as e:
        assert isinstance(e, AuthenticationError)
        assert "Auth failed" in str(e)


def test_clone_or_pull_repo(monkeypatch):
    """Test clone_or_pull_repo handles both clone and pull scenarios."""
    import tempfile

    # Mock environment variables
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    # Mock subprocess.run
    class MockResult:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: MockResult())

    # Should not raise
    repo_path = client.clone_or_pull_repo()
    # New code uses workspace pattern: shared/repo or task_{id}/repo
    assert repo_path == client.temp_base / "shared" / "repo"


def test_ensure_git_config(monkeypatch, tmp_path):
    """Test _ensure_git_config sets git user.name and user.email."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    # Track git config commands
    config_commands = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        if "config" in cmd:
            config_commands.append(cmd)
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    client._ensure_git_config(repo_path)

    # Check that config commands were called
    assert len(config_commands) >= 2
    assert any("user.name" in cmd for cmd in config_commands)
    assert any("user.email" in cmd for cmd in config_commands)


def test_get_default_branch_from_symbolic_ref(monkeypatch, tmp_path):
    """Test _get_default_branch detects branch from symbolic-ref."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")

    client = GiteaClient()

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        class MockResult:
            returncode = 0
            stdout = "refs/remotes/origin/main" if "symbolic-ref" in cmd else ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    branch = client._get_default_branch(repo_path)
    assert branch == "main"


def test_get_default_branch_fallback_to_main(monkeypatch, tmp_path):
    """Test _get_default_branch falls back to 'main' when detection fails."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")

    client = GiteaClient()

    def mock_run(*args, **kwargs):
        class MockResult:
            returncode = 1  # Command fails
            stdout = ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    branch = client._get_default_branch(repo_path)
    assert branch == "main"


def test_git_pull_with_branch_parameter(monkeypatch, tmp_path):
    """Test _git_pull accepts and uses branch parameter."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")

    client = GiteaClient()

    pulled_branches = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        if "pull" in cmd:
            # Extract branch from command: git pull origin <branch>
            if len(cmd) >= 4:
                pulled_branches.append(cmd[3])
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Test with explicit branch
    client._git_pull(repo_path, "main")
    assert "main" in pulled_branches

    # Test with default branch detection
    pulled_branches.clear()
    client._git_pull(repo_path)
    # Should call _get_default_branch which returns 'main' by default


def test_git_push_with_branch_parameter(monkeypatch, tmp_path):
    """Test _git_push accepts and uses branch parameter."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")

    client = GiteaClient()

    pushed_branches = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        if "push" in cmd:
            # Extract branch from command: git push origin <branch>
            if len(cmd) >= 4:
                pushed_branches.append(cmd[3])
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Test with explicit branch
    client._git_push(repo_path, "main")
    assert "main" in pushed_branches


def test_add_skill_folder(monkeypatch):
    """Test add_skill_folder extracts ZIP to correct location."""
    import zipfile
    import tempfile

    # Mock environment variables
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    # Create a test ZIP file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_zip = Path(tmpdir) / "test-skill-1.0.0.zip"

        with zipfile.ZipFile(test_zip, 'w') as zf:
            zf.writestr("skill.md", "# Test Skill\n")
            zf.writestr("script.py", "print('hello')")

        # Create target directory
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()

        folder_name = client.add_skill_folder(
            repo_path,
            test_zip,
            "test-skill",
            "1.0.0"
        )

        assert folder_name == "test-skill-1.0.0"
        skill_path = repo_path / folder_name
        assert skill_path.exists()
        assert (skill_path / "skill.md").exists()
        assert (skill_path / "script.py").exists()


def test_commit_and_push(monkeypatch, tmp_path):
    """Test commit_and_push orchestrates config, add, commit, and push operations."""
    import subprocess

    # Mock environment variables
    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    # Track all git commands
    git_commands = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        git_commands.append(cmd)

        # Set up responses for different commands
        returncode = 0
        stdout = ""
        stderr = ""

        if "symbolic-ref" in cmd:
            # Detect default branch as 'main'
            stdout = "refs/remotes/origin/main"
        elif "commit" in cmd:
            # Return a commit hash
            stdout = "[main abc123def456789] Test commit"
        elif "log" in cmd and "--format=%H" in cmd:
            stdout = "abc123def456789"

        class MockResult:
            pass
        MockResult.returncode = returncode
        MockResult.stdout = stdout
        MockResult.stderr = stderr
        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    commit_hash = client.commit_and_push(
        repo_path,
        "feat: add test-skill-1.0.0"
    )

    assert commit_hash is not None
    # Should have: config user.name, config user.email, add, commit, push
    assert len(git_commands) >= 5
    assert any("config" in cmd and "user.name" in cmd for cmd in git_commands)
    assert any("config" in cmd and "user.email" in cmd for cmd in git_commands)
    assert any("add" in cmd for cmd in git_commands)
    assert any("commit" in cmd for cmd in git_commands)
    assert any("push" in cmd and "-u" in cmd for cmd in git_commands)


def test_git_clone_empty_repository(monkeypatch, tmp_path):
    """Test _git_clone handles empty repository gracefully."""
    import subprocess

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    git_commands = []

    def mock_run(*args, **kwargs):
        cmd = args[0] if args else []
        git_commands.append(cmd)

        if "clone" in cmd:
            # Simulate empty repository error
            class MockResult:
                returncode = 128
                stdout = ""
                stderr = "fatal: couldn't find remote ref master"
        else:
            class MockResult:
                returncode = 0
                stdout = ""
                stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_run)

    repo_path = tmp_path / "test_repo"

    # Should not raise, will initialize empty repo
    client._git_clone("https://localhost:3000/test/repo.git", repo_path)

    # Verify repo was initialized
    assert repo_path.exists()
    # Check that init and remote add were called
    assert any("init" in cmd for cmd in git_commands)
    assert any("remote" in cmd and "add" in cmd for cmd in git_commands)


def test_push_with_retry_success_on_third_attempt(monkeypatch):
    """Test that push_with_retry retries on network errors"""
    import time
    import tempfile

    monkeypatch.setenv("GITEA_REPO_URL", "https://localhost:3000/test/repo.git")
    monkeypatch.setenv("GITEA_TOKEN", "test_token")

    client = GiteaClient()

    attempt = [0]
    def mock_push(*args, **kwargs):
        attempt[0] += 1
        if attempt[0] < 3:
            # Simulate network error on first 2 attempts
            raise NetworkError("Network timeout")
        else:
            # Third attempt succeeds - return a fake commit hash
            return "abc123def456789"

    # Mock the actual push operation
    monkeypatch.setattr(client, "clone_or_pull_repo", lambda: Path("/tmp/repo"))
    monkeypatch.setattr(client, "add_skill_folder", lambda *args: "test-1.0.0")
    monkeypatch.setattr(client, "commit_and_push", mock_push)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_zip = Path(tmpdir) / "test.zip"
        test_zip.touch()

        result = client.push_with_retry(
            test_zip,
            "test",
            "1.0.0",
            max_retries=3
        )

        assert result["success"] is True
        assert result["commit_hash"] == "abc123def456789"  # Mock returns this hash
        assert result["folder"] == "test-1.0.0"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
