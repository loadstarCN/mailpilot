"""测试管理界面 SMTP 配置表单的每天发送上限（max_per_day）解析"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.admin.csrf import generate_csrf_token
from app.admin.deps import get_current_admin, session_manager
from app.db.session import get_db
from app.main import app
from tests.conftest import make_admin, make_smtp_config

FORM = {
    "name": "主发送",
    "host": "smtp.example.com",
    "port": "465",
    "username": "user@example.com",
    "password": "",
    "from_email": "noreply@example.com",
    "from_name": "",
    "max_per_hour": "100",
}


@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_admin] = lambda: make_admin()
    session_token = session_manager.create_session({"admin_id": str(uuid.uuid4())})
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
        cookies={"mp_session": session_token},
    ) as c:
        c.csrf_token = generate_csrf_token(session_token)
        yield c
    app.dependency_overrides.clear()


class TestSmtpConfigFormMaxPerDay:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("submitted", "expected"), [("", None), ("  ", None), ("800", 800)])
    async def test_edit_parses_max_per_day(self, client, submitted, expected):
        """编辑表单：留空 = 不限（None），填数字按数字保存"""
        with patch(
            "app.admin.smtp_configs.smtp_service.update_smtp_config", new_callable=AsyncMock
        ) as mock_update:
            resp = await client.post(
                f"/admin/smtp-configs/{uuid.uuid4()}/edit",
                data={**FORM, "max_per_day": submitted, "_csrf_token": client.csrf_token},
            )

        assert resp.status_code == 303
        assert mock_update.call_args.kwargs["max_per_day"] == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("submitted", "expected"), [(None, None), ("", None), ("1000", 1000)])
    async def test_create_parses_max_per_day(self, client, submitted, expected):
        """新建表单：未提交 / 留空 = 不限（None）"""
        data = {**FORM, "project_id": str(uuid.uuid4()), "_csrf_token": client.csrf_token}
        if submitted is not None:
            data["max_per_day"] = submitted
        with patch(
            "app.admin.smtp_configs.smtp_service.create_smtp_config", new_callable=AsyncMock
        ) as mock_create:
            resp = await client.post("/admin/smtp-configs/create", data=data)

        assert resp.status_code == 303
        assert mock_create.call_args.kwargs["max_per_day"] == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("max_per_day", "expected_value"), [(1000, 'value="1000"'), (None, 'value=""')])
    async def test_edit_form_renders_max_per_day(self, client, max_per_day, expected_value):
        config = make_smtp_config(max_per_day=max_per_day)
        with patch(
            "app.admin.smtp_configs.smtp_service.get_smtp_config", new_callable=AsyncMock
        ) as mock_get, patch(
            "app.admin.smtp_configs.project_service.list_projects", new_callable=AsyncMock
        ) as mock_projects:
            mock_get.return_value = config
            mock_projects.return_value = []
            resp = await client.get(f"/admin/smtp-configs/{config.id}/edit")

        assert resp.status_code == 200
        assert f'name="max_per_day" min="0" {expected_value}' in resp.text

    @pytest.mark.asyncio
    async def test_list_shows_max_per_day(self, client):
        limited = make_smtp_config(max_per_hour=100, max_per_day=1000)
        unlimited = make_smtp_config(max_per_hour=50, max_per_day=None)
        with patch(
            "app.admin.smtp_configs.smtp_service.list_smtp_configs", new_callable=AsyncMock
        ) as mock_list, patch(
            "app.admin.smtp_configs.project_service.list_projects", new_callable=AsyncMock
        ) as mock_projects:
            mock_list.return_value = [limited, unlimited]
            mock_projects.return_value = []
            resp = await client.get("/admin/smtp-configs")

        assert resp.status_code == 200
        assert "100/h" in resp.text and "1000/d" in resp.text
        assert "50/h" in resp.text
        assert resp.text.count("/d</span>") == 1
