"""管理界面功能测试：登录、CSRF 防护"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.admin.csrf import generate_csrf_token
from app.db.session import get_db
from app.main import app


@pytest.fixture
def mock_admin():
    from tests.conftest import make_admin

    return make_admin(id=uuid.UUID("00000000-0000-0000-0000-000000000001"))


@pytest.fixture(autouse=True)
def override_db():
    """所有 admin 测试都 mock 掉数据库依赖"""
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


class TestCsrfToken:
    """CSRF token 生成与验证"""

    def test_generate_token_deterministic(self):
        token1 = generate_csrf_token("session-abc")
        token2 = generate_csrf_token("session-abc")
        assert token1 == token2

    def test_different_sessions_different_tokens(self):
        token1 = generate_csrf_token("session-abc")
        token2 = generate_csrf_token("session-xyz")
        assert token1 != token2

    def test_token_is_hex_string(self):
        token = generate_csrf_token("session-abc")
        assert len(token) == 64  # sha256 hex digest
        int(token, 16)  # 应该是合法的十六进制


class TestCsrfProtection:
    """CSRF 中间件测试"""

    @pytest.mark.asyncio
    async def test_post_without_csrf_token_rejected(self):
        """POST 请求缺少 CSRF token 应被拒绝"""
        # 构造一个有效的 session cookie
        from app.admin.deps import session_manager

        token = session_manager.create_session(
            {"admin_id": "00000000-0000-0000-0000-000000000001"}
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/admin/logout",
                cookies={"mp_session": token},
                data={},  # 没有 _csrf_token
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_post_with_valid_csrf_token_accepted(self):
        """POST 请求带正确 CSRF token 应通过验证"""
        from app.admin.deps import session_manager

        session_token = session_manager.create_session(
            {"admin_id": "00000000-0000-0000-0000-000000000001"}
        )
        csrf_token = generate_csrf_token(session_token)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.post(
                "/admin/logout",
                cookies={"mp_session": session_token},
                data={"_csrf_token": csrf_token},
            )
            # logout 成功后重定向到 login
            assert resp.status_code == 303
            assert "/admin/login" in resp.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_post_with_wrong_csrf_token_rejected(self):
        """POST 请求带错误 CSRF token 应被拒绝"""
        from app.admin.deps import session_manager

        session_token = session_manager.create_session(
            {"admin_id": "00000000-0000-0000-0000-000000000001"}
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/admin/logout",
                cookies={"mp_session": session_token},
                data={"_csrf_token": "wrong-token"},
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_login_exempt_from_csrf(self):
        """登录页面不需要 CSRF token"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            # mock admin_service.authenticate 返回 None（密码错误）
            with patch(
                "app.admin.auth.admin_service.authenticate",
                new_callable=AsyncMock,
                return_value=None,
            ):
                # 即使没有 CSRF token，登录请求也不应返回 403
                resp = await client.post(
                    "/admin/login",
                    data={"username": "wrong", "password": "wrong"},
                )
            # 应该返回登录页面（200 + 错误提示），而不是 403
            assert resp.status_code != 403

    @pytest.mark.asyncio
    async def test_get_requests_not_affected(self):
        """GET 请求不受 CSRF 检查影响"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/admin/login")
            assert resp.status_code == 200


class TestUnauthenticatedAccess:
    """未登录访问测试"""

    @pytest.mark.asyncio
    async def test_dashboard_redirects_to_login(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/admin/dashboard")
            assert resp.status_code == 303
            assert "/admin/login" in resp.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_projects_redirects_to_login(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            resp = await client.get("/admin/projects")
            assert resp.status_code == 303
            assert "/admin/login" in resp.headers.get("location", "")
