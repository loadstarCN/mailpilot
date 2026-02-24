import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import project_service, template_service
from .deps import get_current_admin, get_flash, set_flash

router = APIRouter(prefix="/templates")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def template_list(
    request: Request,
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    pid = uuid.UUID(project_id) if project_id else None
    tpls = await template_service.list_templates(db, pid)
    projects = await project_service.list_projects(db)
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "email_templates/list.html",
        {
            "request": request,
            "admin": admin,
            "templates_list": tpls,
            "projects": projects,
            "selected_project_id": project_id,
            "flash": flash,
        },
    )
    if flash:
        response.delete_cookie("mp_flash")
    return response


@router.get("/create", response_class=HTMLResponse)
async def template_create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    projects = await project_service.list_projects(db)
    return templates.TemplateResponse(
        "email_templates/form.html",
        {"request": request, "admin": admin, "tpl": None, "projects": projects},
    )


@router.post("/create")
async def template_create_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    await template_service.create_template(
        db,
        uuid.UUID(form["project_id"]),
        name=form["name"],
        subject=form["subject"],
        body_html=form["body_html"],
        body_text=form.get("body_text") or None,
        description=form.get("description") or None,
    )
    response = RedirectResponse(url="/admin/templates", status_code=303)
    set_flash(response, "模板创建成功")
    return response


@router.get("/{template_id}/edit", response_class=HTMLResponse)
async def template_edit_form(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    tpl = await template_service.get_template(db, template_id)
    if not tpl:
        return RedirectResponse(url="/admin/templates", status_code=303)
    projects = await project_service.list_projects(db)
    return templates.TemplateResponse(
        "email_templates/form.html",
        {"request": request, "admin": admin, "tpl": tpl, "projects": projects},
    )


@router.post("/{template_id}/edit")
async def template_edit_submit(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    form = await request.form()
    await template_service.update_template(
        db,
        template_id,
        name=form["name"],
        subject=form["subject"],
        body_html=form["body_html"],
        body_text=form.get("body_text") or None,
        description=form.get("description") or None,
        is_active="is_active" in form,
    )
    response = RedirectResponse(url="/admin/templates", status_code=303)
    set_flash(response, "模板更新成功")
    return response


@router.post("/{template_id}/delete")
async def template_delete(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    await template_service.delete_template(db, template_id)
    response = RedirectResponse(url="/admin/templates", status_code=303)
    set_flash(response, "模板已删除")
    return response


@router.post("/{template_id}/preview")
async def template_preview(
    template_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    tpl = await template_service.get_template(db, template_id)
    if not tpl:
        return HTMLResponse("<p>模板不存在</p>", status_code=404)
    form = await request.form()
    import json
    variables = json.loads(form.get("variables", "{}"))
    subject, body_html, body_text = template_service.render_preview(
        tpl.subject, tpl.body_html, tpl.body_text, variables
    )
    return HTMLResponse(body_html)
