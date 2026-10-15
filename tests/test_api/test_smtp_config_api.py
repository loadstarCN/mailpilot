"""测试 SMTP 配置 API 的每天发送上限（max_per_day）"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_project
from app.db.session import get_db
from app.main import app
from tests.conftest import make_project, make_smtp_config

CREATE_BODY = {
    "host": "smtp.example.com",
    "port": 465,
    "username": "user@example.com",
    "password": "secret",
    "from_email": "noreply@example.com",
}


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


class TestSmtpConfigMaxPerDayAPI:
    @pytest.mark.asyncio
    async def test_create_passes_max_per_day(self, client, project):
        config = make_smtp_config(project_id=project.id, max_per_day=1000)
        with patch(
            "app.api.config.smtp_service.create_smtp_config", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = config
            resp = await client.post(
                "/api/v1/config/smtp", json={**CREATE_BODY, "max_per_day": 1000}
            )

        assert resp.status_code == 201
        assert resp.json()["max_per_day"] == 1000
        assert mock_create.call_args.kwargs["max_per_day"] == 1000

    @pytest.mark.asyncio
    async def test_create_defaults_to_unlimited(self, client, project):
        config = make_smtp_config(project_id=project.id)
        with patch(
            "app.api.config.smtp_service.create_smtp_config", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = config
            resp = await client.post("/api/v1/config/smtp", json=CREATE_BODY)

        assert resp.status_code == 201
        assert resp.json()["max_per_day"] is None
        assert mock_create.call_args.kwargs["max_per_day"] is None

    @pytest.mark.asyncio
    async def test_create_rejects_negative(self, client):
        resp = await client.post(
            "/api/v1/config/smtp", json={**CREATE_BODY, "max_per_day": -1}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_passes_explicit_null(self, client, project):
        """PUT 显式传 null：传给 service 以改为不限"""
        config = make_smtp_config(project_id=project.id, max_per_day=1000)
        with patch(
            "app.api.config.smtp_service.get_smtp_config", new_callable=AsyncMock
        ) as mock_get, patch(
            "app.api.config.smtp_service.update_smtp_config", new_callable=AsyncMock
        ) as mock_update:
            mock_get.return_value = config
            mock_update.return_value = make_smtp_config(project_id=project.id)
            resp = await client.put(
                f"/api/v1/config/smtp/{config.id}", json={"max_per_day": None}
            )

        assert resp.status_code == 200
        assert mock_update.call_args.kwargs == {"max_per_day": None}

    @pytest.mark.asyncio
    async def test_update_without_field_does_not_touch(self, client, project):
        """PUT 不传 max_per_day：不传给 service，保持原值"""
        config = make_smtp_config(project_id=project.id, max_per_day=1000)
        with patch(
            "app.api.config.smtp_service.get_smtp_config", new_callable=AsyncMock
        ) as mock_get, patch(
            "app.api.config.smtp_service.update_smtp_config", new_callable=AsyncMock
        ) as mock_update:
            mock_get.return_value = config
            mock_update.return_value = config
            resp = await client.put(
                f"/api/v1/config/smtp/{config.id}", json={"max_per_hour": 50}
            )

        assert resp.status_code == 200
        assert "max_per_day" not in mock_update.call_args.kwargs
