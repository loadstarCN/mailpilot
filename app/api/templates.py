import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project
from ..schemas.template import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
)
from ..services import template_service
from .deps import get_current_project, get_db

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    req: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    tpl = await template_service.create_template(
        db,
        project.id,
        name=req.name,
        subject=req.subject,
        body_html=req.body_html,
        body_text=req.body_text,
        variables=req.variables,
        description=req.description,
    )
    return tpl


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    return await template_service.list_templates(db, project.id)


@router.get("/{name}", response_model=TemplateResponse)
async def get_template(
    name: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    tpl = await template_service.get_template_by_name(db, project.id, name)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@router.put("/{name}", response_model=TemplateResponse)
async def update_template(
    name: str,
    req: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    tpl = await template_service.get_template_by_name(db, project.id, name)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    updated = await template_service.update_template(
        db, tpl.id, **req.model_dump(exclude_unset=True)
    )
    return updated


@router.delete("/{name}")
async def delete_template(
    name: str,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    tpl = await template_service.get_template_by_name(db, project.id, name)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    await template_service.delete_template(db, tpl.id)
    return {"message": "已删除"}


@router.post("/{name}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    name: str,
    req: TemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    tpl = await template_service.get_template_by_name(db, project.id, name)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    subject, body_html, body_text = template_service.render_preview(
        tpl.subject, tpl.body_html, tpl.body_text, req.variables
    )
    return TemplatePreviewResponse(
        subject=subject, body_html=body_html, body_text=body_text
    )
