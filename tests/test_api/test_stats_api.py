"""测试统计和健康检查 API"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_current_project
from app.db.session import get_db
from app.main import app
from tests.conftest import make_project


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


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        with patch("app.api.stats.stats_service.get_overview", new_callable=AsyncMock) as mock_overview:
            mock_overview.return_value = {
                "today": {"total": 100, "success": 95, "failed": 5},
                "week": {"total": 500, "success": 480, "failed": 20},
                "month": {"total": 2000, "success": 1950, "failed": 50},
            }
            resp = await client.get("/api/v1/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["today"]["total"] == 100
        assert data["week"]["success"] == 480
        assert data["month"]["failed"] == 50
