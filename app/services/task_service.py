import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.email_task import EmailTask


async def create_task(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    to_addrs: list[str],
    subject: str,
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    reply_to: str | None = None,
    body_html: str | None = None,
    body_text: str | None = None,
    template_id: str | None = None,
    template_vars: dict | None = None,
    attachments: list | None = None,
    priority: int = 0,
    max_retries: int = 3,
    smtp_config_id: uuid.UUID | None = None,
    webhook_url: str | None = None,
    scheduled_at: datetime | None = None,
) -> EmailTask:
    task = EmailTask(
        project_id=project_id,
        smtp_config_id=smtp_config_id,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        bcc_addrs=bcc_addrs,
        reply_to=reply_to,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        template_id=template_id,
        template_vars=template_vars,
        attachments=attachments,
        priority=priority,
        max_retries=max_retries,
        webhook_url=webhook_url,
        scheduled_at=scheduled_at,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> EmailTask | None:
    stmt = select(EmailTask).where(EmailTask.id == task_id)
    if project_id:
        stmt = stmt.where(EmailTask.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EmailTask], int]:
    stmt = select(EmailTask)
    count_stmt = select(func.count(EmailTask.id))

    if project_id:
        stmt = stmt.where(EmailTask.project_id == project_id)
        count_stmt = count_stmt.where(EmailTask.project_id == project_id)
    if status:
        stmt = stmt.where(EmailTask.status == status)
        count_stmt = count_stmt.where(EmailTask.status == status)

    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(EmailTask.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    return list(result.scalars().all()), total


async def cancel_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> tuple[bool, str]:
    task = await get_task(db, task_id, project_id)
    if not task:
        return False, "任务不存在"
    if task.status not in ("pending", "retry"):
        return False, f"任务状态为 {task.status}，无法取消"
    task.status = "cancelled"
    await db.commit()
    return True, "已取消"


async def retry_task(
    db: AsyncSession, task_id: uuid.UUID, project_id: uuid.UUID | None = None
) -> tuple[bool, str]:
    task = await get_task(db, task_id, project_id)
    if not task:
        return False, "任务不存在"
    if task.status != "failed":
        return False, f"任务状态为 {task.status}，仅 failed 状态可重试"
    task.status = "pending"
    task.retry_count = 0
    task.next_retry_at = None
    task.error = None
    await db.commit()
    return True, "已重新加入队列"
