"""测试模板 API 端点"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_project
from app.db.session import get_db
from app.main import app
from tests.conftest import make_email_template, make_project


@pytest.fixture
def project():
    return make_project()


@pytest.fixture
async def client(project):
    app.dependency_overrides[get_current_project] = lambda: project
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


class TestTemplateAPI:
    @pytest.mark.asyncio
    async def test_create_template(self, client, project):
        tpl = make_email_template(project_id=project.id, name="new_tpl")
        with patch("app.api.templates.template_service.create_template", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = tpl
            resp = await client.post("/api/v1/templates", json={
                "name": "new_tpl",
                "subject": "标题",
                "body_html": "<p>内容</p>",
            })

        assert resp.status_code == 201
        assert resp.json()["name"] == "new_tpl"

    @pytest.mark.asyncio
    async def test_list_templates(self, client, project):
        tpls = [make_email_template(project_id=project.id, name=f"tpl_{i}") for i in range(2)]
        with patch("app.api.templates.template_service.list_templates", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = tpls
            resp = await client.get("/api/v1/templates")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_template_by_name(self, client, project):
        tpl = make_email_template(project_id=project.id, name="welcome")
        with patch("app.api.templates.template_service.get_template_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tpl
            resp = await client.get("/api/v1/templates/welcome")

        assert resp.status_code == 200
        assert resp.json()["name"] == "welcome"

    @pytest.mark.asyncio
    async def test_get_template_not_found(self, client):
        with patch("app.api.templates.template_service.get_template_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resp = await client.get("/api/v1/templates/nonexistent")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preview_template(self, client, project):
        tpl = make_email_template(project_id=project.id)
        with patch("app.api.templates.template_service.get_template_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = tpl
            resp = await client.post("/api/v1/templates/welcome/preview", json={
                "variables": {"username": "张三"},
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "张三" in data["subject"]
        assert "张三" in data["body_html"]

    @pytest.mark.asyncio
    async def test_delete_template(self, client, project):
        tpl = make_email_template(project_id=project.id)
        with (
            patch("app.api.templates.template_service.get_template_by_name", new_callable=AsyncMock) as mock_get,
            patch("app.api.templates.template_service.delete_template", new_callable=AsyncMock) as mock_del,
        ):
            mock_get.return_value = tpl
            mock_del.return_value = True
            resp = await client.delete("/api/v1/templates/welcome")

        assert resp.status_code == 200
