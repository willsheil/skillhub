"""
Database model functions.

This module imports database functions from the root database.py module
to provide a clean API for the rest of the application.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

# Import all database functions from root database module
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from database import (
    init_db,
    get_connection,
    create_skill_record,
    get_pending_skills,
    get_skill_by_id,
    update_skill_status,
    get_user_by_credentials,
    get_user_by_id,
    update_last_login,
    record_download,
    get_download_stats,
    get_stats_with_author,
    get_user_uploads,
    get_total_users_count,
    get_skills_count_by_status,
    get_today_downloads_count,
    get_top_skills_by_downloads,
    get_top_users_by_downloads,
    get_skill_source_type,
    create_notification,
    update_skill_active_status,
    get_skill_active_status,
    get_my_skills,
    set_default_skill_version,
    get_skill_versions,
    get_user_notifications,
    get_unread_notifications_count,
    mark_notification_read,
    mark_all_notifications_read,
    cleanup_old_notifications,
    get_users_list,
    create_user,
    update_user_role,
    disable_user,
    enable_user,
    delete_user,
    reset_user_api_key,
    get_user_skills_count,
    get_default_skill_version,
    get_all_default_skill_versions,
    get_skill_approval_status,
    delete_skill_version,
    batch_unlist_skills,
    batch_delete_skills,
    check_skill_exists,
)

__all__ = [
    "init_db",
    "get_connection",
    "create_skill_record",
    "get_pending_skills",
    "get_skill_by_id",
    "update_skill_status",
    "get_user_by_credentials",
    "get_user_by_id",
    "update_last_login",
    "record_download",
    "get_download_stats",
    "get_stats_with_author",
    "get_user_uploads",
    "get_total_users_count",
    "get_skills_count_by_status",
    "get_today_downloads_count",
    "get_top_skills_by_downloads",
    "get_top_users_by_downloads",
    "get_skill_source_type",
    "create_notification",
    "update_skill_active_status",
    "get_skill_active_status",
    "get_my_skills",
    "set_default_skill_version",
    "get_skill_versions",
    "get_user_notifications",
    "get_unread_notifications_count",
    "mark_notification_read",
    "mark_all_notifications_read",
    "cleanup_old_notifications",
    "get_users_list",
    "create_user",
    "update_user_role",
    "disable_user",
    "enable_user",
    "delete_user",
    "reset_user_api_key",
    "get_user_skills_count",
    "get_default_skill_version",
    "get_all_default_skill_versions",
    "get_skill_approval_status",
    "delete_skill_version",
    "batch_unlist_skills",
    "batch_delete_skills",
    "check_skill_exists",
]
