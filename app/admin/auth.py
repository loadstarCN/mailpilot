from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.session import get_db
from ..services import admin_service
from .deps import session_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
async def login_submit(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    admin = await admin_service.authenticate(db, username, password)
    if not admin:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "用户名或密码错误"},
        )

    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    token = session_manager.create_session({"admin_id": str(admin.id)})
    response.set_cookie(
        session_manager.cookie_name,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(session_manager.cookie_name)
    return response
