import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import project_service, task_service, template_service
from .deps import get_current_admin, get_flash, set_flash

router = APIRouter(prefix="/tasks")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def task_list(
    request: Request,
    status: str | None = None,
    project_id: str | None = None,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    pid = uuid.UUID(project_id) if project_id else None
    items, total = await task_service.list_tasks(
        db, project_id=pid, status=status, page=page, page_size=20
    )
    projects = await project_service.list_projects(db)
    project_map = {str(p.id): p.name for p in projects}
    total_pages = (total + 19) // 20
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "admin": admin,
            "tasks": items,
            "projects": projects,
            "project_map": project_map,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "selected_status": status,
            "selected_project_id": project_id,
            "flash": flash,
        },
    )
    if flash:
        response.delete_cookie("mp_flash")
    return response


@router.post("/{task_id}/retry")
async def task_retry(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    success, msg = await task_service.retry_task(db, task_id)
    response = RedirectResponse(url="/admin/tasks", status_code=303)
    set_flash(response, msg, "success" if success else "error")
    return response


@router.get("/{task_id}/preview")
async def task_preview(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    task = await task_service.get_task(db, task_id)
    if not task:
        return JSONResponse({"error": "任务不存在"}, status_code=404)

    result: dict = {
        "subject": task.subject,
        "to_addrs": list(task.to_addrs or []),
        "cc_addrs": list(task.cc_addrs) if task.cc_addrs else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }

    if not task.template_id:
        # 直接发送：数据库中已有完整内容
        result["type"] = "direct"
        result["body_html"] = task.body_html
        result["body_text"] = task.body_text
    else:
        result["template_vars"] = task.template_vars
        tpl = await template_service.get_template_by_name(
            db, task.project_id, task.template_id
        )
        if not tpl:
            # 模板已删除
            result["type"] = "deleted"
            result["warning"] = "原始模板已删除，无法渲染预览"
            result["body_html"] = None
            result["body_text"] = None
        else:
            # 检查模板是否在任务创建后被修改
            modified = (
                tpl.updated_at and task.created_at
                and tpl.updated_at > task.created_at
            )
            try:
                subject, body_html, body_text = template_service.render_preview(
                    tpl.subject, tpl.body_html, tpl.body_text,
                    task.template_vars or {},
                )
                result["subject"] = subject
                result["body_html"] = body_html
                result["body_text"] = body_text
            except Exception:
                result["body_html"] = None
                result["body_text"] = None
                modified = True  # 渲染失败视为模板有问题

            if modified:
                result["type"] = "modified"
                result["warning"] = "模板在此邮件发送后已被修改，以下内容可能与实际发送不一致"
            else:
                result["type"] = "ok"

    return JSONResponse(result)


@router.post("/{task_id}/cancel")
async def task_cancel(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    success, msg = await task_service.cancel_task(db, task_id)
    response = RedirectResponse(url="/admin/tasks", status_code=303)
    set_flash(response, msg, "success" if success else "error")
    return response
