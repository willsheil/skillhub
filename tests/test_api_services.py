import pytest
from api.v1.services import get_skills_list, get_skill_detail
from database import init_external_api_tables, get_connection

@pytest.fixture(autouse=True)
def setup_test_data():
    """设置测试数据"""
    init_external_api_tables()
    # 清理测试数据
    with get_connection() as conn:
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-api-%'")
        conn.commit()
    yield
    # 清理
    with get_connection() as conn:
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-api-%'")
        conn.commit()

def test_get_skills_list_basic():
    """测试基本列表查询"""
    result = get_skills_list(
        source_type="all",
        page=1,
        page_size=20
    )
    assert "items" in result
    assert "pagination" in result
    assert result["pagination"]["page"] == 1

def test_get_skills_list_with_filter():
    """测试带过滤条件的查询"""
    result = get_skills_list(
        source_type="opensource",
        page=1,
        page_size=20
    )
    # 验证所有返回的技能都是 opensource 类型
    for item in result["items"]:
        assert item["source_type"] == "opensource"

def test_get_skills_list_with_search():
    """测试关键词搜索"""
    result = get_skills_list(
        source_type="all",
        page=1,
        page_size=20,
        keyword="security"
    )
    # 验证返回的技能名称或描述包含关键词
    for item in result["items"]:
        keyword_in_name = "security" in item["name"].lower()
        keyword_in_desc = "security" in item["description"].lower()
        assert keyword_in_name or keyword_in_desc
