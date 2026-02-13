"""
Repository 数据访问层
使用 Tortoise ORM 进行数据库操作
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from core.models import (
    User, Skill, Download, Notification, GiteaPushTask,
    UserRole, UserStatus, SkillStatus, SkillSourceType,
    NotificationType, GiteaTaskStatus,
)


# ============================================================================
# User Repository
# ============================================================================

class UserRepository:
    """用户数据访问层"""

    @staticmethod
    async def get_by_credentials(employee_id: str, api_key: str) -> Optional[User]:
        """通过员工ID和API密钥获取用户"""
        return await User.get_or_none(
            employee_id=employee_id,
            api_key=api_key,
            status=UserStatus.ACTIVE
        )

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        """通过ID获取用户"""
        return await User.get_or_none(id=user_id)

    @staticmethod
    async def get_by_employee_id(employee_id: str) -> Optional[User]:
        """通过员工ID获取用户"""
        return await User.get_or_none(employee_id=employee_id)

    @staticmethod
    async def create(
        employee_id: str,
        api_key: str,
        role: str = UserRole.USER
    ) -> User:
        """创建新用户"""
        user = await User.create(
            employee_id=employee_id,
            api_key=api_key,
            role=role,
            status=UserStatus.ACTIVE
        )
        return user

    @staticmethod
    async def update_last_login(user_id: int) -> None:
        """更新用户最后登录时间"""
        await User.filter(id=user_id).update(last_login=datetime.now())

    @staticmethod
    async def update_role(user_id: int, role: str) -> None:
        """更新用户角色"""
        await User.filter(id=user_id).update(role=role)

    @staticmethod
    async def update_status(user_id: int, status: str) -> None:
        """更新用户状态"""
        await User.filter(id=user_id).update(status=status)

    @staticmethod
    async def reset_api_key(user_id: int, new_key: str) -> None:
        """重置用户API密钥"""
        await User.filter(id=user_id).update(api_key=new_key)

    @staticmethod
    async def disable(user_id: int) -> None:
        """禁用用户"""
        await User.filter(id=user_id).update(status=UserStatus.DISABLED)

    @staticmethod
    async def enable(user_id: int) -> None:
        """启用用户"""
        await User.filter(id=user_id).update(status=UserStatus.ACTIVE)

    @staticmethod
    async def delete(user_id: int) -> None:
        """删除用户"""
        await User.filter(id=user_id).delete()

    @staticmethod
    async def increment_skills_count(user_id: int) -> None:
        """增加用户技能数量"""
        user = await User.get(id=user_id)
        if user:
            user.skills_count += 1
            await user.save()

    @staticmethod
    async def list_all(
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[User]:
        """获取用户列表"""
        query = User.all()
        if status:
            query = query.filter(status=status)
        return await query.offset(offset).limit(limit).prefetch_related([])


# ============================================================================
# Skill Repository
# ============================================================================

class SkillRepository:
    """技能数据访问层"""

    @staticmethod
    async def get_by_id(skill_id: int) -> Optional[Skill]:
        """通过ID获取技能"""
        return await Skill.get_or_none(id=skill_id)

    @staticmethod
    async def get_by_name_and_version(skill_name: str, version: str) -> Optional[Skill]:
        """通过名称和版本获取技能"""
        return await Skill.get_or_none(
            skill_name=skill_name,
            version=version
        )

    @staticmethod
    async def create(
        skill_name: str,
        version: str,
        filename: str,
        uploader_id: int,
        source_type: str = SkillSourceType.OPENSOURCE
    ) -> Skill:
        """创建新技能记录"""
        skill = await Skill.create(
            skill_name=skill_name,
            version=version,
            filename=filename,
            uploader_id=uploader_id,
            source_type=source_type,
            status=SkillStatus.PENDING
        )
        return skill

    @staticmethod
    async def update_status(
        skill_id: int,
        status: str,
        reviewer_id: Optional[int] = None,
        review_comment: Optional[str] = None
    ) -> None:
        """更新技能状态"""
        update_data = {"status": status}
        if status in [SkillStatus.APPROVED, SkillStatus.REJECTED]:
            update_data["reviewed_at"] = datetime.now()
        if reviewer_id:
            update_data["reviewer_id"] = reviewer_id
        if review_comment:
            update_data["review_comment"] = review_comment

        await Skill.filter(id=skill_id).update(**update_data)

    @staticmethod
    async def update_active_status(skill_id: int, is_active: bool) -> None:
        """更新技能激活状态"""
        await Skill.filter(id=skill_id).update(is_active=is_active)

    @staticmethod
    async def get_pending_skills() -> List[Skill]:
        """获取待审核技能列表"""
        return await Skill.filter(
            status=SkillStatus.PENDING
        ).prefetch_related(["uploader"]).all()

    @staticmethod
    async def get_by_uploader(
        uploader_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Skill]:
        """获取上传者的技能列表"""
        return await Skill.filter(
            uploader_id=uploader_id
        ).offset(offset).limit(limit).all()

    @staticmethod
    async def update_push_task_id(skill_id: int, task_id: int) -> None:
        """更新技能的最新推送任务ID"""
        await Skill.filter(id=skill_id).update(latest_push_task_id=task_id)

    @staticmethod
    async def set_default_version(skill_id: int) -> None:
        """设置技能为默认版本"""
        # 先取消该技能其他版本的默认设置
        await Skill.filter(
            skill_name=Skill.get(id=skill_id).skill_name
        ).update(default_version=False)
        # 设置该版本为默认
        await Skill.filter(id=skill_id).update(default_version=True)

    @staticmethod
    async def get_versions(skill_name: str) -> List[Skill]:
        """获取技能的所有版本"""
        return await Skill.filter(skill_name=skill_name).all()

    @staticmethod
    async def get_default_version(skill_name: str) -> Optional[Skill]:
        """获取技能的默认版本"""
        return await Skill.get_or_none(
            skill_name=skill_name,
            default_version=True
        )

    @staticmethod
    async def batch_unlist(skill_ids: List[int]) -> None:
        """批量下架技能"""
        await Skill.filter(id__in=skill_ids).update(
            status=SkillStatus.UNLISTED,
            is_active=False
        )

    @staticmethod
    async def batch_delete(skill_ids: List[int]) -> None:
        """批量删除技能"""
        await Skill.filter(id__in=skill_ids).delete()

    @staticmethod
    async def get_all_active(
        limit: int = 100,
        offset: int = 0
    ) -> List[Skill]:
        """获取所有激活的技能"""
        return await Skill.filter(
            is_active=True,
            status__in=[SkillStatus.APPROVED]
        ).offset(offset).limit(limit).all()

    @staticmethod
    async def count_by_status(status: str) -> int:
        """统计指定状态的技能数量"""
        return await Skill.filter(status=status).count()


# ============================================================================
# Download Repository
# ============================================================================

class DownloadRepository:
    """下载数据访问层"""

    @staticmethod
    async def create(
        skill_name: str,
        version: str,
        filename: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Download:
        """记录下载"""
        download = await Download.create(
            skill_name=skill_name,
            version=version,
            filename=filename,
            ip_address=ip_address,
            user_agent=user_agent,
            user_id=user_id
        )
        return download

    @staticmethod
    async def get_stats(days: int = 30) -> List[Dict]:
        """获取下载统计"""
        since = datetime.now() - timedelta(days=days)
        downloads = await Download.filter(
            downloaded_at__gte=since
        ).all()

        # 统计每个技能的下载量
        stats = {}
        for download in downloads:
            key = f"{download.skill_name}:{download.version}"
            if key not in stats:
                stats[key] = {
                    "skill_name": download.skill_name,
                    "version": download.version,
                    "count": 0
                }
            stats[key]["count"] += 1

        return sorted(stats.values(), key=lambda x: x["count"], reverse=True)

    @staticmethod
    async def get_top_skills(limit: int = 10, days: int = 30) -> List[Dict]:
        """获取热门技能"""
        since = datetime.now() - timedelta(days=days)
        downloads = await Download.filter(
            downloaded_at__gte=since
        ).all()

        # 统计
        skill_counts = {}
        for download in downloads:
            if download.skill_name not in skill_counts:
                skill_counts[download.skill_name] = 0
            skill_counts[download.skill_name] += 1

        # 排序并返回
        top_skills = [
            {"skill_name": name, "downloads": count}
            for name, count in sorted(
                skill_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
        ]
        return top_skills[:limit]

    @staticmethod
    async def get_top_users(limit: int = 10, days: int = 30) -> List[Dict]:
        """获取下载量最多的用户"""
        since = datetime.now() - timedelta(days=days)
        downloads = await Download.filter(
            downloaded_at__gte=since,
            user_id__isnull=False
        ).prefetch_related(["user"]).all()

        # 统计每个用户的技能下载量
        user_skill_counts = {}
        for download in downloads:
            if download.user_id not in user_skill_counts:
                user_skill_counts[download.user_id] = {
                    "user_id": download.user_id,
                    "employee_id": download.user.employee_id if download.user else "",
                    "count": 0
                }
            user_skill_counts[download.user_id]["count"] += 1

        # 排序并返回
        top_users = sorted(
            user_skill_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        return top_users[:limit]

    @staticmethod
    async def count_today() -> int:
        """统计今日下载量"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return await Download.filter(downloaded_at__gte=today).count()

    @staticmethod
    async def count_total() -> int:
        """统计总下载量"""
        return await Download.all().count()

    @staticmethod
    async def get_by_user(
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Download]:
        """获取用户下载记录"""
        return await Download.filter(
            user_id=user_id
        ).order_by("-downloaded_at").offset(offset).limit(limit).all()


# ============================================================================
# Notification Repository
# ============================================================================

class NotificationRepository:
    """通知数据访问层"""

    @staticmethod
    async def create(
        user_id: int,
        type: str,
        title: str,
        content: Optional[str] = None,
        related_skill_id: Optional[int] = None
    ) -> Notification:
        """创建通知"""
        notification = await Notification.create(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            related_skill_id=related_skill_id
        )
        return notification

    @staticmethod
    async def get_by_user(
        user_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """获取用户通知"""
        query = Notification.filter(user_id=user_id)
        if unread_only:
            query = query.filter(is_read=False)
        return await query.order_by("-created_at").limit(limit).prefetch_related(["related_skill"])

    @staticmethod
    async def get_unread_count(user_id: int) -> int:
        """获取用户未读通知数"""
        return await Notification.filter(
            user_id=user_id,
            is_read=False
        ).count()

    @staticmethod
    async def mark_as_read(notification_id: int, user_id: int) -> None:
        """标记通知为已读"""
        await Notification.filter(
            id=notification_id,
            user_id=user_id
        ).update(is_read=True)

    @staticmethod
    async def mark_all_as_read(user_id: int) -> None:
        """标记用户所有通知为已读"""
        await Notification.filter(
            user_id=user_id,
            is_read=False
        ).update(is_read=True)

    @staticmethod
    async def cleanup_old(days: int = 30) -> int:
        """清理旧通知"""
        cutoff = datetime.now() - timedelta(days=days)
        count = await Notification.filter(
            created_at__lt=cutoff,
            is_read=True
        ).count()
        await Notification.filter(
            created_at__lt=cutoff,
            is_read=True
        ).delete()
        return count


# ============================================================================
# Statistics Repository
# ============================================================================

class StatsRepository:
    """统计数据访问层"""

    @staticmethod
    async def get_overall() -> Dict:
        """获取总体统计"""
        total_users = await User.filter(status=UserStatus.ACTIVE).count()
        total_downloads = await Download.all().count()
        pending_skills = await Skill.filter(status=SkillStatus.PENDING).count()
        approved_skills = await Skill.filter(status=SkillStatus.APPROVED).count()

        return {
            "total_users": total_users,
            "total_downloads": total_downloads,
            "pending_skills": pending_skills,
            "approved_skills": approved_skills,
            "total_skills": pending_skills + approved_skills,
        }

    @staticmethod
    async def get_skills_with_authors() -> Dict:
        """获取技能列表及作者信息"""
        skills = await Skill.filter(
            status=SkillStatus.APPROVED
        ).prefetch_related(["uploader"]).all()

        skill_author_map = {}
        for skill in skills:
            if skill.uploader:
                skill_author_map[skill.skill_name] = skill.uploader.employee_id
            else:
                skill_author_map[skill.skill_name] = "Unknown"

        return skill_author_map


# ============================================================================
# Gitea Push Task Repository
# ============================================================================

class GiteaPushTaskRepository:
    """Gitea推送任务数据访问层"""

    @staticmethod
    async def create(
        skill_id: int,
        skill_name: str,
        version: str
    ) -> GiteaPushTask:
        """创建推送任务"""
        task = await GiteaPushTask.create(
            skill_id=skill_id,
            skill_name=skill_name,
            version=version,
            status=GiteaTaskStatus.PENDING
        )
        return task

    @staticmethod
    async def get_by_id(task_id: int) -> Optional[GiteaPushTask]:
        """通过ID获取任务"""
        return await GiteaPushTask.get_or_none(id=task_id)

    @staticmethod
    async def get_pending_tasks(limit: int = 10) -> List[GiteaPushTask]:
        """获取待处理任务"""
        return await GiteaPushTask.filter(
            status__in=[GiteaTaskStatus.PENDING, GiteaTaskStatus.RETRY_PENDING]
        ).order_by("created_at").limit(limit).all()

    @staticmethod
    async def update_status(
        task_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """更新任务状态"""
        update_data = {"status": status}
        if status == GiteaTaskStatus.PUSHING:
            update_data["started_at"] = datetime.now()
        elif status in [GiteaTaskStatus.SUCCESS, GiteaTaskStatus.FAILED]:
            update_data["completed_at"] = datetime.now()
        if error_message:
            update_data["error_message"] = error_message

        await GiteaPushTask.filter(id=task_id).update(**update_data)

    @staticmethod
    async def increment_retry(task_id: int) -> None:
        """增加任务重试次数"""
        task = await GiteaPushTask.get(id=task_id)
        task.retry_count += 1
        await task.save()

    @staticmethod
    async def reserve_task(task_id: int) -> None:
        """预留任务（防止重复处理）"""
        await GiteaPushTask.filter(
            id=task_id,
            status=GiteaTaskStatus.PENDING
        ).update(status=GiteaTaskStatus.RESERVED)
