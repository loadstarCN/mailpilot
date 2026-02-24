import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project
from ..schemas.task import TaskListResponse, TaskResponse
from ..services import task_service
from .deps import get_current_project, get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    task = await task_service.get_task(db, task_id, project.id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


TaskStatus = Literal["pending", "processing", "sent", "failed", "retry", "cancelled"]


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: TaskStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    items, total = await task_service.list_tasks(
        db, project_id=project.id, status=status, page=page, page_size=page_size
    )
    return TaskListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    success, msg = await task_service.cancel_task(db, task_id, project.id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    success, msg = await task_service.retry_task(db, task_id, project.id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}
