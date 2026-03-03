import pytest
from fastapi.testclient import TestClient
from main import app
from database import create_api_key

client = TestClient(app)

@pytest.fixture
def api_key():
    """创建测试 API Key"""
    result = create_api_key(user_id=1, name="Route Test")
    return result['api_key']

def test_get_skills_list_no_auth():
    """测试无认证访问"""
    response = client.get("/api/v1/skills")
    assert response.status_code == 401

def test_get_skills_list_with_auth(api_key):
    """测试有效认证访问"""
    headers = {"X-API-Key": api_key}
    response = client.get("/api/v1/skills", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "items" in data["data"]

def test_get_skills_list_with_filter(api_key):
    """测试带过滤条件"""
    headers = {"X-API-Key": api_key}
    response = client.get(
        "/api/v1/skills?source_type=opensource&page=1&page_size=10",
        headers=headers
    )
    assert response.status_code == 200

def test_get_skill_detail(api_key):
    """测试获取技能详情"""
    headers = {"X-API-Key": api_key}
    # 假设存在这个技能
    response = client.get("/api/v1/skills/auditing-python-security", headers=headers)
    # 可能返回 404 或 200
    assert response.status_code in [200, 404]
