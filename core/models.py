"""
Tortoise ORM Models for SkillHub
定义所有数据库表模型
"""

from tortoise import fields
from tortoise.models import Model
from datetime import datetime
from typing import Optional, List


class UserRole:
    """用户角色枚举"""
    ADMIN = "admin"
    USER = "user"
    REVIEWER = "reviewer"


class UserStatus:
    """用户状态枚举"""
    ACTIVE = "active"
    DISABLED = "disabled"


class SkillStatus:
    """技能状态枚举"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNLISTED = "unlisted"


class SkillSourceType:
    """技能来源类型枚举"""
    OPENSOURCE = "opensource"
    ICSL = "icsl"
    HUAWEI = "huawei"


class NotificationType:
    """通知类型枚举"""
    SKILL_APPROVED = "skill_approved"
    SKILL_REJECTED = "skill_rejected"
    SKILL_DOWNLOAD = "skill_download"
    SYSTEM_NOTICE = "system_notice"


class GiteaTaskStatus:
    """Gitea推送任务状态枚举"""
    PENDING = "pending"
    RESERVED = "reserved"
    PUSHING = "pushing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"


class User(Model):
    """用户表"""
    id = fields.IntField(pk=True)
    employee_id = fields.CharField(max_length=20, unique=True)
    api_key = fields.CharField(max_length=255)
    role = fields.CharField(max_length=20, default=UserRole.USER)
    status = fields.CharField(max_length=20, default=UserStatus.ACTIVE)
    skills_count = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)

    class Meta:
        table = "users"
        ordering = ["-created_at"]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "api_key": self.api_key,
            "role": self.role,
            "status": self.status,
            "skills_count": self.skills_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Skill(Model):
    """技能表"""
    id = fields.IntField(pk=True)
    skill_name = fields.CharField(max_length=255)
    version = fields.CharField(max_length=50)
    filename = fields.CharField(max_length=255)
    uploader: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="uploaded_skills"
    )
    status = fields.CharField(max_length=20, default=SkillStatus.PENDING)
    source_type = fields.CharField(max_length=20, default=SkillSourceType.OPENSOURCE)
    is_active = fields.BooleanField(default=True)
    uploaded_at = fields.DatetimeField(auto_now_add=True)
    reviewed_at = fields.DatetimeField(null=True)
    reviewer_id = fields.IntField(null=True)
    review_comment = fields.CharField(max_length=255, null=True)
    default_version = fields.BooleanField(default=False)
    latest_push_task_id = fields.IntField(null=True)

    class Meta:
        table = "skills"
        ordering = ["-uploaded_at"]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "version": self.version,
            "filename": self.filename,
            "uploader_id": self.uploader_id,
            "status": self.status,
            "source_type": self.source_type,
            "is_active": self.is_active,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "default_version": self.default_version,
        }


class Download(Model):
    """下载记录表"""
    id = fields.IntField(pk=True)
    skill_name = fields.CharField(max_length=255)
    version = fields.CharField(max_length=50)
    filename = fields.CharField(max_length=255)
    downloaded_at = fields.DatetimeField(auto_now_add=True)
    ip_address = fields.CharField(max_length=255, null=True)
    user_agent = fields.CharField(max_length=255, null=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="downloads", null=True
    )

    class Meta:
        table = "downloads"
        ordering = ["-downloaded_at"]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "version": self.version,
            "filename": self.filename,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "user_id": self.user_id,
        }


class Notification(Model):
    """通知表"""
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="notifications"
    )
    type = fields.CharField(max_length=50)
    title = fields.CharField(max_length=255)
    content = fields.TextField(null=True)
    related_skill: fields.ForeignKeyRelation[Skill] = fields.ForeignKeyField(
        "models.Skill", related_name="notifications", null=True
    )
    is_read = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notifications"
        ordering = ["-created_at"]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "related_skill_id": self.related_skill_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GiteaPushTask(Model):
    """Gitea推送任务表"""
    id = fields.IntField(pk=True)
    skill: fields.ForeignKeyRelation[Skill] = fields.ForeignKeyField(
        "models.Skill", related_name="push_tasks"
    )
    skill_name = fields.CharField(max_length=255)
    version = fields.CharField(max_length=50)
    status = fields.CharField(
        max_length=20,
        default=GiteaTaskStatus.PENDING,
    )
    retry_count = fields.IntField(default=0)
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    started_at = fields.DatetimeField(null=True)
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "gitea_push_tasks"
        ordering = ["-created_at"]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "version": self.version,
            "status": self.status,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
