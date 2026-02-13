"""
ORM Repository 单元测试

测试 Tortoise ORM 的 Repository 层功能
"""

import pytest
from tortoise import Tortoise
from core.models import User, Skill, Download, Notification, GiteaPushTask
from core.repositories import (
    UserRepository, SkillRepository, DownloadRepository,
    NotificationRepository, GiteaPushTaskRepository,
)
from core.db_config import DB_CONFIG


# ============================================================================
# 测试配置
# ============================================================================

@pytest.fixture
async def db():
    """初始化测试数据库"""
    await Tortoise.init(config=DB_CONFIG, _create_db=True)
    yield
    await Tortoise.close_connections()


@pytest.fixture
async def clean_db(db):
    """每个测试后清理数据"""
    yield
    await User.all().delete()
    await Skill.all().delete()
    await Download.all().delete()
    await Notification.all().delete()
    await GiteaPushTask.all().delete()


# ============================================================================
# UserRepository 测试
# ============================================================================

@pytest.mark.asyncio
async def test_create_user(db, clean_db):
    """测试创建用户"""
    user = await UserRepository.create(
        employee_id="test001",
        api_key="test_key_123",
        role="user"
    )

    assert user.id is not None
    assert user.employee_id == "test001"
    assert user.api_key == "test_key_123"
    assert user.role == "user"
    assert user.status == "active"


@pytest.mark.asyncio
async def test_get_user_by_credentials(db, clean_db):
    """测试通过凭证获取用户"""
    # 先创建用户
    await UserRepository.create(
        employee_id="test002",
        api_key="test_key_456",
        role="user"
    )

    # 测试获取
    user = await UserRepository.get_by_credentials("test002", "test_key_456")

    assert user is not None
    assert user.employee_id == "test002"


@pytest.mark.asyncio
async def test_get_user_by_credentials_invalid(db, clean_db):
    """测试无效凭证获取用户"""
    user = await UserRepository.get_by_credentials("invalid", "invalid")

    assert user is None


@pytest.mark.asyncio
async def test_update_last_login(db, clean_db):
    """测试更新最后登录时间"""
    user = await UserRepository.create(
        employee_id="test003",
        api_key="test_key_789",
        role="user"
    )

    assert user.last_login is None

    # 更新最后登录时间
    await UserRepository.update_last_login(user.id)

    # 重新获取用户验证
    updated_user = await UserRepository.get_by_id(user.id)
    assert updated_user.last_login is not None


# ============================================================================
# SkillRepository 测试
# ============================================================================

@pytest.mark.asyncio
async def test_create_skill(db, clean_db):
    """测试创建技能"""
    # 先创建用户
    user = await UserRepository.create(
        employee_id="test004",
        api_key="test_key_abc",
        role="user"
    )

    # 创建技能
    skill = await SkillRepository.create(
        skill_name="test_skill",
        version="1.0.0",
        filename="test_skill.zip",
        uploader_id=user.id,
        source_type="opensource"
    )

    assert skill.id is not None
    assert skill.skill_name == "test_skill"
    assert skill.version == "1.0.0"
    assert skill.uploader_id == user.id
    assert skill.status == "pending"


@pytest.mark.asyncio
async def test_update_skill_status(db, clean_db):
    """测试更新技能状态"""
    # 创建用户和技能
    user = await UserRepository.create(
        employee_id="test005",
        api_key="test_key_def",
        role="reviewer"
    )
    skill = await SkillRepository.create(
        skill_name="test_skill2",
        version="1.0.0",
        filename="test_skill2.zip",
        uploader_id=user.id,
        source_type="opensource"
    )

    # 更新为审核通过
    await SkillRepository.update_status(
        skill.id,
        "approved",
        reviewer_id=user.id
    )

    # 验证更新
    updated = await SkillRepository.get_by_id(skill.id)
    assert updated.status == "approved"
    assert updated.reviewer_id == user.id


@pytest.mark.asyncio
async def test_get_pending_skills(db, clean_db):
    """测试获取待审核技能"""
    # 创建用户
    user = await UserRepository.create(
        employee_id="test006",
        api_key="test_key_ghi",
        role="user"
    )

    # 创建多个技能
    await SkillRepository.create(
        skill_name="pending_skill1",
        version="1.0.0",
        filename="pending1.zip",
        uploader_id=user.id
    )
    await SkillRepository.create(
        skill_name="pending_skill2",
        version="1.0.0",
        filename="pending2.zip",
        uploader_id=user.id
    )
    await SkillRepository.create(
        skill_name="approved_skill",
        version="1.0.0",
        filename="approved.zip",
        uploader_id=user.id
    )
    # 审核其中一个
    approved_skill = await Skill.get(skill_name="approved_skill")
    approved_skill.status = "approved"
    await approved_skill.save()

    # 获取待审核列表
    pending = await SkillRepository.get_pending_skills()

    assert len(pending) == 2
    for skill in pending:
        assert skill.status == "pending"


# ============================================================================
# DownloadRepository 测试
# ============================================================================

@pytest.mark.asyncio
async def test_record_download(db, clean_db):
    """测试记录下载"""
    # 创建用户
    user = await UserRepository.create(
        employee_id="test007",
        api_key="test_key_jkl",
        role="user"
    )

    # 记录下载
    download = await DownloadRepository.create(
        skill_name="test_download_skill",
        version="1.0.0",
        filename="test.zip",
        ip_address="127.0.0.1",
        user_agent="test-agent",
        user_id=user.id
    )

    assert download.id is not None
    assert download.skill_name == "test_download_skill"
    assert download.user_id == user.id


# ============================================================================
# NotificationRepository 测试
# ============================================================================

@pytest.mark.asyncio
async def test_create_notification(db, clean_db):
    """测试创建通知"""
    # 创建用户
    user = await UserRepository.create(
        employee_id="test008",
        api_key="test_key_mno",
        role="user"
    )

    # 创建通知
    notification = await NotificationRepository.create(
        user_id=user.id,
        type="skill_approved",
        title="技能审核通过",
        content="您的技能 test_skill 已通过审核"
    )

    assert notification.id is not None
    assert notification.user_id == user.id
    assert notification.type == "skill_approved"
    assert notification.is_read is False


@pytest.mark.asyncio
async def test_mark_as_read(db, clean_db):
    """测试标记通知为已读"""
    user = await UserRepository.create(
        employee_id="test009",
        api_key="test_key_pqr",
        role="user"
    )

    notification = await NotificationRepository.create(
        user_id=user.id,
        type="system_notice",
        title="系统通知"
    )

    assert notification.is_read is False

    # 标记为已读
    await NotificationRepository.mark_as_read(notification.id, user.id)

    # 验证
    updated = await Notification.get(id=notification.id)
    assert updated.is_read is True


# ============================================================================
# GiteaPushTaskRepository 测试
# ============================================================================

@pytest.mark.asyncio
async def test_create_push_task(db, clean_db):
    """测试创建推送任务"""
    # 创建用户和技能
    user = await UserRepository.create(
        employee_id="test010",
        api_key="test_key_stu",
        role="user"
    )
    skill = await SkillRepository.create(
        skill_name="test_push_skill",
        version="1.0.0",
        filename="push.zip",
        uploader_id=user.id
    )

    # 创建推送任务
    task = await GiteaPushTaskRepository.create(
        skill_id=skill.id,
        skill_name="test_push_skill",
        version="1.0.0"
    )

    assert task.id is not None
    assert task.skill_id == skill.id
    assert task.status == "pending"


@pytest.mark.asyncio
async def test_update_task_status(db, clean_db):
    """测试更新任务状态"""
    user = await UserRepository.create(
        employee_id="test011",
        api_key="test_key_vwx",
        role="user"
    )
    skill = await SkillRepository.create(
        skill_name="test_push_skill2",
        version="1.0.0",
        filename="push2.zip",
        uploader_id=user.id
    )

    task = await GiteaPushTaskRepository.create(
        skill_id=skill.id,
        skill_name="test_push_skill2",
        version="1.0.0"
    )

    # 更新状态为推送中
    await GiteaPushTaskRepository.update_status(task.id, "pushing")

    # 验证更新
    updated = await GiteaPushTask.get(id=task.id)
    assert updated.status == "pushing"


# ============================================================================
# 集成测试
# ============================================================================

@pytest.mark.asyncio
async def test_user_skill_workflow(db, clean_db):
    """测试用户上传技能的完整流程"""
    # 1. 创建用户
    user = await UserRepository.create(
        employee_id="workflow_test",
        api_key="workflow_key",
        role="user"
    )

    # 2. 用户上传技能
    skill = await SkillRepository.create(
        skill_name="workflow_skill",
        version="1.0.0",
        filename="workflow.zip",
        uploader_id=user.id
    )

    # 3. 获取用户的技能列表
    user_skills = await SkillRepository.get_by_uploader(user.id)
    assert len(user_skills) == 1
    assert user_skills[0].skill_name == "workflow_skill"

    # 4. 审核通过技能
    await SkillRepository.update_status(
        skill.id,
        "approved",
        reviewer_id=user.id  # 假设用户是审核员
    )

    # 5. 设置为默认版本
    await SkillRepository.set_default_version(skill.id)

    # 验证默认版本
    default_skill = await SkillRepository.get_default_version("workflow_skill")
    assert default_skill is not None
    assert default_skill.id == skill.id
    assert default_skill.default_version is True
