"""测试基础设施：fixtures 和公共工具"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---- 工厂函数：创建测试用 model 替身（SimpleNamespace）----
# 使用 SimpleNamespace 而非真实 SQLAlchemy model，避免 ORM 属性描述符的初始化问题


def make_project(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "name": "测试项目",
        "api_key": "test-api-key-" + uuid.uuid4().hex[:16],
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_smtp_config(project_id=None, **kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "name": "测试SMTP",
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "encrypted-password",
        "use_tls": True,
        "from_email": "noreply@example.com",
        "from_name": "Test",
        "max_per_hour": 100,
        "is_default": True,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_email_task(project_id=None, **kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "smtp_config_id": None,
        "to_addrs": ["user@example.com"],
        "cc_addrs": None,
        "bcc_addrs": None,
        "reply_to": None,
        "subject": "测试邮件",
        "body_html": "<p>Hello</p>",
        "body_text": None,
        "template_id": None,
        "template_vars": None,
        "attachments": None,
        "priority": 0,
        "status": "pending",
        "retry_count": 0,
        "max_retries": 3,
        "next_retry_at": None,
        "error": None,
        "webhook_url": None,
        "created_at": datetime.now(timezone.utc),
        "scheduled_at": None,
        "processing_at": None,
        "sent_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_email_template(project_id=None, **kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "name": "welcome",
        "subject": "欢迎 {{ username }}",
        "body_html": "<h1>你好 {{ username }}</h1>",
        "body_text": "你好 {{ username }}",
        "variables": [{"name": "username", "required": True}],
        "description": "欢迎邮件",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_admin(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "username": "admin",
        "password_hash": "$2b$12$fake_hash_for_testing",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "last_login_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---- Mock DB Session ----


@pytest.fixture
def mock_db():
    """创建一个 mock AsyncSession"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    return db
