"""
集中测试配置和 fixture。

解决测试隔离问题：
- 统一管理 dependency_overrides
- 统一管理测试用户 ID
- 统一管理数据库 setup/cleanup
"""

import sys
import os
# 将 tests 目录添加到 sys.path，以便导入 test_shared 模块
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db
import zipfile
import io
import base64
import json


# 使用与 main.py 相同的 SECRET_KEY
SECRET_KEY = "your-secret-key-change-this"

# 从共享模块导入（使用模块访问，而非直接导入变量）
import test_shared


def encode_session(data: dict) -> str:
    """编码 session 数据为 cookie 值，使用与 Starlette SessionMiddleware 相同的方式。"""
    # Starlette 使用 itsdangerous 的 URLSafeTimedSerializer
    # 参见: https://github.com/encode/starlette/blob/master/starlette/middleware/sessions.py
    from itsdangerous import URLSafeTimedSerializer
    # SessionMiddleware 默认使用 salt="cookie-session"
    serializer = URLSafeTimedSerializer(
        SECRET_KEY,
        salt="cookie-session",
        signer_kwargs={"key_derivation": "hmac", "digest_method": "sha512"}
    )
    return serializer.dumps(data)


# 统一的认证覆盖函数
def override_get_current_user(request: Request):
    # 使用 test_shared 的 getter 函数获取当前值（而非导入变量）
    uid = test_shared.get_test_user_id()
    role = test_shared.get_test_user_role()
    uid = uid if uid else 1
    role = role if role else "user"
    # 设置 session 以便后续代码可以使用
    request.session["user_id"] = uid
    request.session["role"] = role
    return {"id": uid, "employee_id": "test-user", "role": role}


def override_require_auth(request: Request):
    # 使用 test_shared 的 getter 函数获取当前值（而非导入变量）
    uid = test_shared.get_test_user_id()
    role = test_shared.get_test_user_role()
    uid = uid if uid else 1
    role = role if role else "user"
    # 设置 session 以便后续代码可以使用
    request.session["user_id"] = uid
    request.session["role"] = role
    # 返回完整的用户字典，模拟 get_user_by_id 的返回值
    return {
        "id": uid,
        "employee_id": "test-user",
        "api_key": "test-api-key",
        "role": role,
        "status": 1,
        "skills_count": 0,
        "created_at": None,
        "last_login": None
    }


def override_require_admin(request: Request):
    # 使用 test_shared 的 getter 函数获取当前值（而非导入变量）
    uid = test_shared.get_test_user_id()
    uid = uid if uid else 1
    # 设置 session 以便后续代码可以使用
    request.session["user_id"] = uid
    request.session["role"] = "admin"
    return True


# 设置全局 dependency overrides
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[require_auth] = override_require_auth
app.dependency_overrides[require_admin] = override_require_admin


@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    """Session 级别设置：初始化数据库。"""
    init_db()
    yield


@pytest.fixture(autouse=True)
def reset_test_state():
    """每个测试前重置测试状态并清理测试数据。"""
    # 先清理测试数据，确保干净的测试环境
    cleanup_test_data("test-")
    test_shared.reset_test_user()
    # 确保使用统一的 override
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_auth] = override_require_auth
    app.dependency_overrides[require_admin] = override_require_admin
    yield
    # 测试后再次清理
    cleanup_test_data("test-")
    test_shared.reset_test_user()


class AuthenticatedTestClient:
    """带认证的 TestClient 包装器。"""

    def __init__(self, app, user_id: int, role: str = "user"):
        self._client = TestClient(app)
        self.user_id = user_id
        self.role = role
        # 生成 session cookie
        session_data = {"user_id": user_id, "role": role}
        self.session_cookie = encode_session(session_data)

    def _add_auth_cookie(self, kwargs):
        """添加认证 cookie 到请求。"""
        headers = dict(kwargs.pop("headers", {}) or {})
        cookies = headers.get("Cookie", "")
        session_cookie_str = f"session={self.session_cookie}"
        if cookies:
            cookies = f"{cookies}; {session_cookie_str}"
        else:
            cookies = session_cookie_str
        headers["Cookie"] = cookies
        kwargs["headers"] = headers
        return kwargs

    def get(self, url, **kwargs):
        return self._client.get(url, **self._add_auth_cookie(kwargs))

    def post(self, url, **kwargs):
        return self._client.post(url, **self._add_auth_cookie(kwargs))

    def put(self, url, **kwargs):
        return self._client.put(url, **self._add_auth_cookie(kwargs))

    def delete(self, url, **kwargs):
        return self._client.delete(url, **self._add_auth_cookie(kwargs))

    def patch(self, url, **kwargs):
        return self._client.patch(url, **self._add_auth_cookie(kwargs))


@pytest.fixture
def client():
    """提供 TestClient。"""
    return TestClient(app)


@pytest.fixture
def auth_client():
    """提供带认证的 TestClient 工厂。"""
    def _create_auth_client(user_id: int, role: str = "user"):
        return AuthenticatedTestClient(app, user_id, role)
    return _create_auth_client


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0",
                         author: str = "w00000001") -> bytes:
    """创建一个最小有效的技能 ZIP 文件用于测试。"""
    skill_md_content = f"""---
name: {skill_name}
description: A test skill for automated testing
metadata:
  version: {version}
  author: {author}
license: MIT
compatibility: Claude Code 1.0+
---

# {skill_name}

This is a test skill for automated testing.
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SKILL.md", skill_md_content)
    zip_buffer.seek(0)
    return zip_buffer.read()


def create_test_user(employee_id: str, role: str = "user") -> int:
    """创建测试用户并返回用户 ID。同时设置认证覆盖。"""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES (%s, %s, %s, 1, 0)
            """,
            (employee_id, f"key_{employee_id}", role)
        )
        user_id = cursor.lastrowid
        conn.commit()
    test_shared.set_test_user_id(user_id, role)
    return user_id


def cleanup_test_data(prefix: str = "test-"):
    """清理测试数据。按外键依赖顺序删除。"""
    with get_connection() as conn:
        # 1. 先获取测试用户 ID
        test_user_ids = conn.execute(
            f"SELECT id FROM users WHERE employee_id LIKE '{prefix}%'"
        ).fetchall()
        test_user_id_list = [u["id"] for u in test_user_ids]

        if test_user_id_list:
            # 2. 删除这些用户上传的所有技能的相关数据
            placeholders = ",".join(["%s"] * len(test_user_id_list))
            # 删除通知
            conn.execute(
                f"DELETE FROM notifications WHERE related_skill_id IN "
                f"(SELECT id FROM skills WHERE uploader_id IN ({placeholders}))",
                test_user_id_list
            )
            # 删除 Gitea 推送任务（按 skill_name）
            conn.execute(
                f"DELETE FROM gitea_push_tasks WHERE skill_name IN "
                f"(SELECT skill_name FROM skills WHERE uploader_id IN ({placeholders}))",
                test_user_id_list
            )
            # 删除下载记录
            conn.execute(
                f"DELETE FROM downloads WHERE skill_name IN "
                f"(SELECT skill_name FROM skills WHERE uploader_id IN ({placeholders}))",
                test_user_id_list
            )
            # 3. 删除这些用户上传的所有技能
            conn.execute(
                f"DELETE FROM skills WHERE uploader_id IN ({placeholders})",
                test_user_id_list
            )
            # 4. 删除外部 API 密钥
            conn.execute(
                f"DELETE FROM external_api_keys WHERE user_id IN ({placeholders})",
                test_user_id_list
            )
            # 5. 最后删除用户
            conn.execute(
                f"DELETE FROM users WHERE id IN ({placeholders})",
                test_user_id_list
            )

        # 6. 同时清理以 prefix 开头的技能（可能是孤立的）
        conn.execute(f"DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE '{prefix}%')")
        conn.execute(f"DELETE FROM gitea_push_tasks WHERE skill_name LIKE '{prefix}%'")
        conn.execute(f"DELETE FROM downloads WHERE skill_name LIKE '{prefix}%'")
        conn.execute(f"DELETE FROM skills WHERE skill_name LIKE '{prefix}%'")

        conn.commit()
