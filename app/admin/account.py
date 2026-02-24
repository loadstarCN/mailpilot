from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import admin_service
from .deps import get_current_admin, get_flash, set_flash

router = APIRouter(prefix="/account")
templates = Jinja2Templates(directory="templates")


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "account/change_password.html",
        {"request": request, "admin": admin, "flash": flash},
    )
    if flash:
        response.delete_cookie("mp_flash")
    return response


@router.post("/change-password")
async def change_password_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    old_password = form.get("old_password", "")
    new_password = form.get("new_password", "")
    confirm_password = form.get("confirm_password", "")

    if new_password != confirm_password:
        return templates.TemplateResponse(
            "account/change_password.html",
            {
                "request": request,
                "admin": admin,
                "error": "两次输入的新密码不一致",
            },
        )

    success, message = await admin_service.change_password(
        db, admin.id, old_password, new_password
    )

    if not success:
        return templates.TemplateResponse(
            "account/change_password.html",
            {
                "request": request,
                "admin": admin,
                "error": message,
            },
        )

    response = RedirectResponse(url="/admin/account/change-password", status_code=303)
    set_flash(response, message)
    return response
