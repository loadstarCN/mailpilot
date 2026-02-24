import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project
from ..models.smtp_config import SmtpConfig
from ..schemas.send import SendRequest, SendResponse, SendTemplateRequest
from ..services import task_service, template_service
from .deps import get_current_project, get_db

router = APIRouter(tags=["send"])


async def _resolve_smtp_config(
    db: AsyncSession, project: Project, smtp_config_ref: str | None
) -> uuid.UUID | None:
    if not smtp_config_ref:
        return None
    # 尝试按 UUID 查找
    try:
        config_id = uuid.UUID(smtp_config_ref)
        config = await db.get(SmtpConfig, config_id)
        if config and config.project_id == project.id:
            return config.id
    except ValueError:
        pass
    # 按 name 查找
    result = await db.execute(
        select(SmtpConfig).where(
            SmtpConfig.project_id == project.id,
            SmtpConfig.name == smtp_config_ref,
            SmtpConfig.is_active.is_(True),
        )
    )
    config = result.scalar_one_or_none()
    if config:
        return config.id
    raise HTTPException(status_code=400, detail=f"SMTP 配置 '{smtp_config_ref}' 不存在")


@router.post("/send", response_model=SendResponse)
async def send_email(
    req: SendRequest,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    if not req.body_html and not req.body_text:
        raise HTTPException(status_code=400, detail="body_html 和 body_text 至少提供一个")

    smtp_config_id = await _resolve_smtp_config(db, project, req.smtp_config)

    task = await task_service.create_task(
        db,
        project.id,
        to_addrs=[str(e) for e in req.to],
        cc_addrs=[str(e) for e in req.cc] if req.cc else None,
        bcc_addrs=[str(e) for e in req.bcc] if req.bcc else None,
        reply_to=str(req.reply_to) if req.reply_to else None,
        subject=req.subject,
        body_html=req.body_html,
        body_text=req.body_text,
        priority=req.priority,
        max_retries=req.max_retries,
        smtp_config_id=smtp_config_id,
        webhook_url=req.webhook_url,
        scheduled_at=req.scheduled_at,
    )
    return SendResponse(task_id=task.id, status=task.status)


@router.post("/send/template", response_model=SendResponse)
async def send_with_template(
    req: SendTemplateRequest,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_current_project),
):
    # 验证模板存在
    tpl = await template_service.get_template_by_name(db, project.id, req.template)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"模板 '{req.template}' 不存在")

    smtp_config_id = await _resolve_smtp_config(db, project, req.smtp_config)

    task = await task_service.create_task(
        db,
        project.id,
        to_addrs=[str(e) for e in req.to],
        cc_addrs=[str(e) for e in req.cc] if req.cc else None,
        bcc_addrs=[str(e) for e in req.bcc] if req.bcc else None,
        reply_to=str(req.reply_to) if req.reply_to else None,
        subject=tpl.subject,
        template_id=req.template,
        template_vars=req.variables,
        priority=req.priority,
        max_retries=req.max_retries,
        smtp_config_id=smtp_config_id,
        webhook_url=req.webhook_url,
        scheduled_at=req.scheduled_at,
    )
    return SendResponse(task_id=task.id, status=task.status)
