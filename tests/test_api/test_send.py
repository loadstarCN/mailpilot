"""测试发送 API 端点"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_project
from app.db.session import get_db
from app.main import app
from tests.conftest import make_email_task, make_project


@pytest.fixture
def project():
    return make_project(name="API测试项目")


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
async def client(project, mock_db_session):
    """创建测试客户端，覆盖认证和 DB 依赖"""
    app.dependency_overrides[get_current_project] = lambda: project
    app.dependency_overrides[get_db] = lambda: mock_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestSendEndpoint:
    @pytest.mark.asyncio
    async def test_send_success(self, client, project):
        task = make_email_task(project_id=project.id, status="pending")

        with patch("app.api.send.task_service.create_task", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = task
            resp = await client.post("/api/v1/send", json={
                "to": ["user@example.com"],
                "subject": "测试",
                "body_html": "<p>Hello</p>",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_send_requires_body(self, client):
        resp = await client.post("/api/v1/send", json={
            "to": ["user@example.com"],
            "subject": "测试",
        })
        assert resp.status_code == 400
        assert "body_html" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_send_with_template(self, client, project):
        task = make_email_task(project_id=project.id, template_id="welcome")

        with (
            patch("app.api.send.template_service.get_template_by_name", new_callable=AsyncMock) as mock_tpl,
            patch("app.api.send.task_service.create_task", new_callable=AsyncMock) as mock_create,
        ):
            from tests.conftest import make_email_template
            mock_tpl.return_value = make_email_template(project_id=project.id)
            mock_create.return_value = task
            resp = await client.post("/api/v1/send/template", json={
                "to": ["user@example.com"],
                "template": "welcome",
                "variables": {"username": "张三"},
            })

        assert resp.status_code == 200
        assert resp.json()["task_id"] == str(task.id)

    @pytest.mark.asyncio
    async def test_send_template_not_found(self, client):
        with patch("app.api.send.template_service.get_template_by_name", new_callable=AsyncMock) as mock_tpl:
            mock_tpl.return_value = None
            resp = await client.post("/api/v1/send/template", json={
                "to": ["user@example.com"],
                "template": "nonexistent",
            })

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_invalid_email(self, client):
        resp = await client.post("/api/v1/send", json={
            "to": ["not-an-email"],
            "subject": "测试",
            "body_html": "<p>Hello</p>",
        })
        assert resp.status_code == 422  # Pydantic 验证失败


class TestTaskEndpoints:
    @pytest.mark.asyncio
    async def test_get_task(self, client, project):
        task = make_email_task(project_id=project.id)
        with patch("app.api.tasks.task_service.get_task", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = task
            resp = await client.get(f"/api/v1/tasks/{task.id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(task.id)

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client):
        with patch("app.api.tasks.task_service.get_task", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resp = await client.get(f"/api/v1/tasks/{uuid.uuid4()}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tasks(self, client, project):
        tasks = [make_email_task(project_id=project.id) for _ in range(3)]
        with patch("app.api.tasks.task_service.list_tasks", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = (tasks, 3)
            resp = await client.get("/api/v1/tasks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, client, project):
        task_id = uuid.uuid4()
        with patch("app.api.tasks.task_service.cancel_task", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = (True, "已取消")
            resp = await client.post(f"/api/v1/tasks/{task_id}/cancel")

        assert resp.status_code == 200
        assert resp.json()["message"] == "已取消"

    @pytest.mark.asyncio
    async def test_cancel_task_invalid_status(self, client):
        task_id = uuid.uuid4()
        with patch("app.api.tasks.task_service.cancel_task", new_callable=AsyncMock) as mock_cancel:
            mock_cancel.return_value = (False, "任务状态为 sent，无法取消")
            resp = await client.post(f"/api/v1/tasks/{task_id}/cancel")

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_task_success(self, client):
        task_id = uuid.uuid4()
        with patch("app.api.tasks.task_service.retry_task", new_callable=AsyncMock) as mock_retry:
            mock_retry.return_value = (True, "已重新加入队列")
            resp = await client.post(f"/api/v1/tasks/{task_id}/retry")

        assert resp.status_code == 200
