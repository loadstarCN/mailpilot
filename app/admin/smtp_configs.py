import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import project_service, smtp_service
from .deps import get_current_admin, get_flash, set_flash

router = APIRouter(prefix="/smtp-configs")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def smtp_config_list(
    request: Request,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        pid = uuid.UUID(project_id) if project_id else None
    except ValueError:
        pid = None
    configs = await smtp_service.list_smtp_configs(db, pid)
    projects = await project_service.list_projects(db)
    project_map = {str(p.id): p.name for p in projects}
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "smtp_configs/list.html",
        {
            "request": request,
            "admin": admin,
            "configs": configs,
            "projects": projects,
            "project_map": project_map,
            "selected_project_id": project_id,
            "flash": flash,
        },
    )
    if flash:
        response.delete_cookie("mp_flash")
    return response


@router.get("/create", response_class=HTMLResponse)
async def smtp_config_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    projects = await project_service.list_projects(db)
    return templates.TemplateResponse(
        "smtp_configs/form.html",
        {"request": request, "admin": admin, "config": None, "projects": projects},
    )


@router.post("/create")
async def smtp_config_create_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    try:
        project_id = uuid.UUID(form.get("project_id", ""))
    except ValueError:
        projects = await project_service.list_projects(db)
        return templates.TemplateResponse(
            "smtp_configs/form.html",
            {"request": request, "admin": admin, "config": None, "projects": projects, "error": "请选择有效的项目"},
            status_code=400,
        )
    await smtp_service.create_smtp_config(
        db,
        project_id,
        name=form.get("name") or None,
        host=form.get("host", ""),
        port=int(form.get("port", 587)),
        username=form.get("username", ""),
        password=form.get("password", ""),
        use_tls="use_tls" in form,
        use_ssl="use_ssl" in form,
        from_email=form.get("from_email", ""),
        from_name=form.get("from_name") or None,
        max_per_hour=int(form.get("max_per_hour", 100)),
        is_default="is_default" in form,
    )
    response = RedirectResponse(url="/admin/smtp-configs", status_code=303)
    set_flash(response, "SMTP 配置创建成功")
    return response


@router.get("/{config_id}/edit", response_class=HTMLResponse)
async def smtp_config_edit_form(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    config = await smtp_service.get_smtp_config(db, config_id)
    if not config:
        return RedirectResponse(url="/admin/smtp-configs", status_code=303)
    projects = await project_service.list_projects(db)
    return templates.TemplateResponse(
        "smtp_configs/form.html",
        {"request": request, "admin": admin, "config": config, "projects": projects},
    )


@router.post("/{config_id}/edit")
async def smtp_config_edit_submit(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    kwargs = {
        "name": form.get("name") or None,
        "host": form.get("host", ""),
        "port": int(form.get("port", 587)),
        "username": form.get("username", ""),
        "use_tls": "use_tls" in form,
        "use_ssl": "use_ssl" in form,
        "from_email": form.get("from_email", ""),
        "from_name": form.get("from_name") or None,
        "max_per_hour": int(form.get("max_per_hour", 100)),
        "is_default": "is_default" in form,
        "is_active": "is_active" in form,
    }
    password = form.get("password", "")
    if password:
        kwargs["password"] = password
    await smtp_service.update_smtp_config(db, config_id, **kwargs)
    response = RedirectResponse(url="/admin/smtp-configs", status_code=303)
    set_flash(response, "SMTP 配置更新成功")
    return response


@router.post("/{config_id}/delete")
async def smtp_config_delete(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    await smtp_service.delete_smtp_config(db, config_id)
    response = RedirectResponse(url="/admin/smtp-configs", status_code=303)
    set_flash(response, "SMTP 配置已删除")
    return response


@router.post("/{config_id}/test")
async def smtp_config_test(
    config_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    success, message = await smtp_service.test_connection(db, config_id)
    response = RedirectResponse(url="/admin/smtp-configs", status_code=303)
    set_flash(response, message, "success" if success else "error")
    return response
