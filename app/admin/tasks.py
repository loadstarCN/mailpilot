import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models.admin import Admin
from ..services import project_service, task_service
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
    total_pages = (total + 19) // 20
    flash = get_flash(request)
    response = templates.TemplateResponse(
        "tasks/list.html",
        {
            "request": request,
            "admin": admin,
            "tasks": items,
            "projects": projects,
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
