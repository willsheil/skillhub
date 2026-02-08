"""
Tests for GiteaClient module.

Tests cover:
- Client initialization with environment variables
- Exception hierarchy
- Basic configuration validation
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
    assert client.temp_dir.exists()
    assert client.temp_dir.name == "gitea_sync"


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
    assert client.temp_dir.exists()


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
    assert repo_path == client.temp_dir / "repo"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
