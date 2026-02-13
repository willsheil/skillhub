"""
集成测试 - API 端到端测试

完整的 API 端到端测试场景，验证所有功能正常工作
"""

import pytest
import httpx
from typing import Dict, List


# ============================================================================
# 测试配置
# ============================================================================

BASE_URL = "http://localhost:28000"
API_V1_PREFIX = "/api/v1"

# 测试用户凭据
TEST_USER = {
    "employee_id": "test_user_001",
    "api_key": "test_key_1234567890abcdef"
}

# 测试管理员凭据
TEST_ADMIN = {
    "employee_id": "admin_user",
    "api_key": "admin_key_9876543210abcdef"
}


# ============================================================================
# 固定 fixtures
# ============================================================================

@pytest.fixture
async def http_client():
    """创建 HTTP 客户端"""
    async with httpx.AsyncClient(app=main_app, base_url=BASE_URL) as client:
        yield client


@pytest.fixture
async def test_user_token(http_client: httpx.AsyncClient):
    """获取用户 token"""
    # 登录获取 token
    response = await http_client.post(f"{API_V1_PREFIX}/auth/login", json={
        "employee_id": TEST_USER["employee_id"],
        "api_key": TEST_USER["api_key"]
    })

    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    yield data["token"]


@pytest.fixture
async def admin_token(http_client: httpx.AsyncClient):
    """获取管理员 token"""
    response = await http_client.post(f"{API_V1_PREFIX}/auth/login", json={
        "employee_id": TEST_ADMIN["employee_id"],
        "api_key": TEST_ADMIN["api_key"]
    })

    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    yield data["token"]


# ============================================================================
# 技能管理测试
# ============================================================================


@pytest.mark.asyncio
async def test_get_skills_list(http_client: httpx.AsyncClient):
    """测试获取技能列表"""
    response = await http_client.get(f"{API_V1_PREFIX}/skills")

    assert response.status_code == 200
    data = response.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)


@pytest.mark.asyncio
async def test_upload_skill(
    http_client: httpx.AsyncClient,
    test_user_token: str
):
    """测试上传技能"""
    # 准备测试文件
    files = {"file": ("skill.zip", b"test content")}

    data = {
        "skill_name": "test_skill",
        "version": "1.0.0",
        "source_type": "opensource"
    }

    response = await http_client.post(
        f"{API_V1_PREFIX}/skills/upload",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    result = response.json()
    assert "skill_id" in result
    assert result["message"] == "技能上传成功，等待审核"


@pytest.mark.asyncio
async def test_download_skill(
    http_client: httpx.AsyncClient,
    test_user_token: str
):
    """测试下载技能"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/skills/download/1",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    # 下载可能返回文件或 404
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_search_skills(http_client: httpx.AsyncClient, test_user_token: str):
    """测试搜索技能"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/skills/name/test",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "skills" in data


# ============================================================================
# 用户管理测试
# ============================================================================


@pytest.mark.asyncio
async def test_get_my_skills(
    http_client: httpx.AsyncClient,
    test_user_token: str
):
    """测试获取我的技能列表"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/my-skills",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "skills" in data


@pytest.mark.asyncio
async def test_delete_my_skill(
    http_client: httpx.AsyncClient,
    test_user_token: str
):
    """测试删除我的技能"""
    # 先上传测试技能
    upload_response = await http_client.post(
        f"{API_V1_PREFIX}/skills/upload",
        json={
            "skill_name": "to_delete",
            "version": "1.0.0",
            "source_type": "opensource"
        },
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert upload_response.status_code == 200
    skill_data = upload_response.json()
    skill_id = skill_data.get("skill_id")

    # 删除技能
    delete_response = await http_client.delete(
        f"{API_V1_PREFIX}/my-skills/{skill_id}",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert delete_response.status_code == 200


# ============================================================================
# 统计 API 测试
# ============================================================================


@pytest.mark.asyncio
async def test_get_overall_stats(http_client: httpx.AsyncClient):
    """测试获取总体统计"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/stats",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "total_users" in data
    assert "total_downloads" in data


@pytest.mark.asyncio
async def test_get_hot_skills(http_client: httpx.AsyncClient, test_user_token: str):
    """测试获取热门技能"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/stats/hot?days=30&limit=10",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "hot_skills" in data


@pytest.mark.asyncio
async def test_download_stats(
    http_client: httpx.AsyncClient,
    test_user_token: str
):
    """测试下载统计"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/stats/downloads?days=30",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "stats" in data


# ============================================================================
# 管理员功能测试
# ============================================================================


@pytest.mark.asyncio
async def test_get_pending_skills(
    http_client: httpx.AsyncClient,
    admin_token: str
):
    """测试获取待审核技能"""
    response = await http_client.get(
        f"{API_V1_PREFIX}/pending",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "skills" in data


@pytest.mark.asyncio
async def test_approve_skill(
    http_client: httpx.AsyncClient,
    admin_token: str
):
    """测试审核通过技能"""
    # 先创建待审核技能
    upload_response = await http_client.post(
        f"{API_V1_PREFIX}/skills/upload",
        json={
            "skill_name": "approve_test",
            "version": "1.0.0",
            "source_type": "opensource"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert upload_response.status_code == 200
    skill_data = upload_response.json()
    skill_id = skill_data.get("skill_id")

    # 审核通过
    response = await http_client.post(
        f"{API_V1_PREFIX}/review/{skill_id}",
        json={"action": "approve", "comment": "测试通过"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_skill(
    http_client: httpx.AsyncClient,
    admin_token: str
):
    """测试审核拒绝技能"""
    upload_response = await http_client.post(
        f"{API_V1_PREFIX}/skills/upload",
        json={
            "skill_name": "reject_test",
            "version": "1.0.0",
            "source_type": "opensource"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert upload_response.status_code == 200
    skill_data = upload_response.json()
    skill_id = skill_data.get("skill_id")

    # 审核拒绝
    response = await http_client.post(
        f"{API_V1_PREFIX}/review/{skill_id}",
        json={"action": "reject", "comment": "测试拒绝"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "rejected"


# ============================================================================
# 集成测试场景
# ============================================================================


@pytest.mark.asyncio
async def test_complete_user_workflow(
    http_client: httpx.AsyncClient
):
    """测试完整用户工作流"""
    # 1. 登录
    login_response = await http_client.post(f"{API_V1_PREFIX}/auth/login", json={
        "employee_id": TEST_USER["employee_id"],
        "api_key": TEST_USER["api_key"]
    })

    assert login_response.status_code == 200
    token = login_response.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 获取技能列表
    skills_response = await http_client.get(f"{API_V1_PREFIX}/skills")
    assert skills_response.status_code == 200

    # 3. 上传技能
    upload_response = await http_client.post(
        f"{API_V1_PREFIX}/skills/upload",
        json={
            "skill_name": "workflow_test",
            "version": "1.0.0",
            "source_type": "opensource"
        },
        headers=headers
    )
    assert upload_response.status_code == 200

    skill_id = upload_response.json()["skill_id"]

    # 4. 获取我的技能
    my_skills_response = await http_client.get(f"{API_V1_PREFIX}/my-skills")
    assert my_skills_response.status_code == 200
    my_skills = my_skills_response.json()["skills"]
    assert len(my_skills) >= 1

    # 5. 删除技能
    delete_response = await http_client.delete(
        f"{API_V1_PREFIX}/my-skills/{skill_id}",
        headers=headers
    )
    assert delete_response.status_code == 200


@pytest.mark.asyncio
async def test_complete_admin_workflow(
    http_client: httpx.AsyncClient
):
    """测试完整管理员工作流"""
    # 1. 管理员登录
    login_response = await http_client.post(f"{API_V1_PREFIX}/auth/login", json={
        "employee_id": TEST_ADMIN["employee_id"],
        "api_key": TEST_ADMIN["api_key"]
    })

    assert login_response.status_code == 200
    token = login_response.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 获取待审核列表
    pending_response = await http_client.get(f"{API_V1_PREFIX}/pending")
    assert pending_response.status_code == 200

    # 3. 审核第一个技能
    pending = pending_response.json()["skills"]
    if pending:
        skill_id = pending[0]["id"]

        response = await http_client.post(
            f"{API_V1_PREFIX}/review/{skill_id}",
            json={"action": "approve", "comment": "自动审核通过"},
            headers=headers
        )
        assert response.status_code == 200

    # 4. 验证技能状态更新
    skills_response = await http_client.get(f"{API_V1_PREFIX}/skills")
    assert skills_response.status_code == 200


# ============================================================================
# 测试辅助函数
# ============================================================================


def assert_skill_data(data: Dict, expected_fields: List[str]):
    """断言技能数据包含预期字段"""
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
    assert data[field] is not None, f"Field {field} should not be None"


# 注意: 这些测试需要 FastAPI app 在测试中运行
# 使用 pytest fixture 注入 app
