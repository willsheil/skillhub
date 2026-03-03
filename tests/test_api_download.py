import pytest
from fastapi.testclient import TestClient
from main import app
from database import create_api_key

client = TestClient(app)

@pytest.fixture
def api_key():
    """创建测试 API Key"""
    result = create_api_key(user_id=1, name="Download Test")
    return result['api_key']

def test_download_skill_no_auth():
    """测试无认证下载"""
    response = client.get("/api/v1/skills/test-skill/download")
    assert response.status_code == 401

def test_download_skill_with_auth(api_key):
    """测试有效认证下载"""
    headers = {"X-API-Key": api_key}
    response = client.get("/api/v1/skills/auditing-python-security/download", headers=headers)
    # 可能返回 404（技能不存在）或 200（存在）
    assert response.status_code in [200, 404]

def test_download_skill_with_version(api_key):
    """测试指定版本下载"""
    headers = {"X-API-Key": api_key}
    response = client.get(
        "/api/v1/skills/auditing-python-security/download?version=1.0.0",
        headers=headers
    )
    assert response.status_code in [200, 404]
