from urllib.parse import quote, unquote

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.session import SessionManager
from ..db.session import get_db
from ..models.admin import Admin

session_manager = SessionManager(
    settings.effective_session_secret, settings.session_max_age
)


async def get_current_admin(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Admin:
    token = request.cookies.get(session_manager.cookie_name)
    if not token:
        from fastapi.responses import RedirectResponse

        raise _RedirectToLogin()
    data = session_manager.load_session(token)
    if not data or "admin_id" not in data:
        raise _RedirectToLogin()
    admin = await db.get(Admin, data["admin_id"])
    if not admin or not admin.is_active:
        raise _RedirectToLogin()
    return admin


class _RedirectToLogin(Exception):
    pass


def set_flash(response: Response, message: str, category: str = "success") -> None:
    # URL 编码，避免中文等非 latin-1 字符导致 cookie 编码错误
    encoded = quote(f"{category}:{message}", safe=":")
    response.set_cookie("mp_flash", encoded, max_age=10, httponly=True, secure=True)


def get_flash(request: Request) -> tuple[str, str] | None:
    value = request.cookies.get("mp_flash")
    if value and ":" in value:
        category, message = unquote(value).split(":", 1)
        return category, message
    return None
