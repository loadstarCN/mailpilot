import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project
from ..schemas.smtp_config import (
    SmtpConfigCreate,
    SmtpConfigResponse,
    SmtpConfigUpdate,
    SmtpTestResponse,
)
from ..services import smtp_service
from .deps import get_current_project, get_db

router = APIRouter(prefix="/config/smtp", tags=["config"])


@router.get("", response_model=list[SmtpConfigResponse])
async def list_smtp_configs(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    return await smtp_service.list_smtp_configs(db, project.id)


@router.post("", response_model=SmtpConfigResponse, status_code=201)
async def create_smtp_config(
    req: SmtpConfigCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    config = await smtp_service.create_smtp_config(
        db,
        project.id,
        name=req.name,
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        use_tls=req.use_tls,
        from_email=str(req.from_email),
        from_name=req.from_name,
        max_per_hour=req.max_per_hour,
        is_default=req.is_default,
    )
    return config


@router.put("/{config_id}", response_model=SmtpConfigResponse)
async def update_smtp_config(
    config_id: uuid.UUID,
    req: SmtpConfigUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    existing = await smtp_service.get_smtp_config(db, config_id)
    if not existing or existing.project_id != project.id:
        raise HTTPException(status_code=404, detail="配置不存在")
    updated = await smtp_service.update_smtp_config(
        db, config_id, **req.model_dump(exclude_unset=True)
    )
    return updated


@router.post("/{config_id}/test", response_model=SmtpTestResponse)
async def test_smtp_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    existing = await smtp_service.get_smtp_config(db, config_id)
    if not existing or existing.project_id != project.id:
        raise HTTPException(status_code=404, detail="配置不存在")
    success, message = await smtp_service.test_connection(db, config_id)
    return SmtpTestResponse(success=success, message=message)
