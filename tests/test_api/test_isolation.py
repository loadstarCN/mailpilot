"""数据隔离测试：验证项目 A 的 API Key 不能访问项目 B 的数据"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_project
from app.db.session import get_db
from app.main import app
from tests.conftest import make_email_task, make_email_template, make_project


@pytest.fixture
def project_a():
    return make_project(
        id=uuid.UUID("aaaa0000-0000-0000-0000-000000000001"),
        name="项目A",
        api_key="key-a",
    )


@pytest.fixture
def project_b():
    return make_project(
        id=uuid.UUID("bbbb0000-0000-0000-0000-000000000002"),
        name="项目B",
        api_key="key-b",
    )


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
async def client_a(project_a, mock_db_session):
    """项目 A 的客户端"""
    app.dependency_overrides[get_current_project] = lambda: project_a
    app.dependency_overrides[get_db] = lambda: mock_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestTaskIsolation:
    @pytest.mark.asyncio
    async def test_task_list_filtered_by_project(self, client_a, project_a, project_b):
        """任务列表只返回当前项目的任务"""
        task_a = make_email_task(project_id=project_a.id, subject="项目A的任务")
        task_b = make_email_task(project_id=project_b.id, subject="项目B的任务")

        with patch(
            "app.api.tasks.task_service.list_tasks", new_callable=AsyncMock
        ) as mock_list:
            # 模拟 service 层只返回项目 A 的任务（因为 service 层按 project_id 过滤）
            mock_list.return_value = ([task_a], 1)
            resp = await client_a.get("/api/v1/tasks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        # 验证 service 层被正确传入了 project_id
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs[1].get("project_id") == project_a.id

    @pytest.mark.asyncio
    async def test_send_creates_task_for_own_project(
        self, client_a, project_a, project_b
    ):
        """发送邮件只关联到自己的项目"""
        task = make_email_task(project_id=project_a.id)

        with patch(
            "app.api.send.task_service.create_task", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = task
            resp = await client_a.post(
                "/api/v1/send",
                json={
                    "to": ["user@example.com"],
                    "subject": "测试",
                    "body_html": "<p>Hello</p>",
                },
            )

        assert resp.status_code == 200
        # 验证 create_task 传入的 project_id 是项目 A 的（第二个位置参数）
        mock_create.assert_called_once()
        call_args = mock_create.call_args[0]
        assert call_args[1] == project_a.id


class TestTemplateIsolation:
    @pytest.mark.asyncio
    async def test_template_list_filtered_by_project(
        self, client_a, project_a, project_b
    ):
        """模板列表只返回当前项目的模板"""
        tpl_a = make_email_template(project_id=project_a.id, name="welcome")

        with patch(
            "app.api.templates.template_service.list_templates",
            new_callable=AsyncMock,
        ) as mock_list:
            mock_list.return_value = [tpl_a]
            resp = await client_a.get("/api/v1/templates")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # 验证 service 层传入了正确的 project_id（第二个位置参数）
        mock_list.assert_called_once()
        call_args = mock_list.call_args[0]
        assert call_args[1] == project_a.id

    @pytest.mark.asyncio
    async def test_get_template_by_name_scoped_to_project(
        self, client_a, project_a, project_b
    ):
        """通过名称获取模板只返回当前项目的"""
        tpl_a = make_email_template(project_id=project_a.id, name="reset_password")

        with patch(
            "app.api.templates.template_service.get_template_by_name",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = tpl_a
            resp = await client_a.get("/api/v1/templates/reset_password")

        assert resp.status_code == 200
        # 验证查询时传入了项目 A 的 ID
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0]
        assert call_args[1] == project_a.id  # 第二个参数是 project_id
