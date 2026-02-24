import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import project_service
from .deps import get_current_admin, get_flash, set_flash

router = APIRouter(prefix="/projects")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def project_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    projects = await project_service.list_projects(db)
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "projects/list.html",
        {"request": request, "admin": admin, "projects": projects, "flash": flash},
    )
    if flash:
        response.delete_cookie("mp_flash")
    return response


@router.get("/create", response_class=HTMLResponse)
async def project_create_form(
    request: Request, admin: Admin = Depends(get_current_admin)
):
    return templates.TemplateResponse(
        "projects/form.html",
        {"request": request, "admin": admin, "project": None},
    )


@router.post("/create")
async def project_create_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    await project_service.create_project(db, name=form["name"])
    response = RedirectResponse(url="/admin/projects", status_code=303)
    set_flash(response, "项目创建成功")
    return response


@router.get("/{project_id}/edit", response_class=HTMLResponse)
async def project_edit_form(
    project_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    project = await project_service.get_project(db, project_id)
    if not project:
        return RedirectResponse(url="/admin/projects", status_code=303)
    return templates.TemplateResponse(
        "projects/form.html",
        {"request": request, "admin": admin, "project": project},
    )


@router.post("/{project_id}/edit")
async def project_edit_submit(
    project_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    await project_service.update_project(
        db, project_id, name=form.get("name"), is_active="is_active" in form
    )
    response = RedirectResponse(url="/admin/projects", status_code=303)
    set_flash(response, "项目更新成功")
    return response


@router.post("/{project_id}/delete")
async def project_delete(
    project_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    await project_service.delete_project(db, project_id)
    response = RedirectResponse(url="/admin/projects", status_code=303)
    set_flash(response, "项目已删除")
    return response


@router.post("/{project_id}/regenerate-key")
async def project_regenerate_key(
    project_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    await project_service.regenerate_api_key(db, project_id)
    response = RedirectResponse(url="/admin/projects", status_code=303)
    set_flash(response, "API Key 已重新生成")
    return response
