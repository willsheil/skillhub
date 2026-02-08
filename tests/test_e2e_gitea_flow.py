import pytest
from pathlib import Path
import tempfile
import zipfile
from gitea_push_service import GiteaPushService
from database import get_connection, init_db

@pytest.fixture
def setup_test_env():
    """Setup test environment with approved skill"""
    init_db()

    # Create test ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
        with zipfile.ZipFile(f.name, 'w') as zf:
            zf.writestr("skill.md", "# Test Skill")

        test_zip = Path(f.name)

    yield test_zip

    # Cleanup
    test_zip.unlink()

def test_full_push_workflow(setup_test_env):
    """Test complete workflow: approval -> push task -> background service -> success"""
    # This would require a test Gitea instance
    # Mark as integration test that can be run manually
    pytest.skip("Requires test Gitea instance")
