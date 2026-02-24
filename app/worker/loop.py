import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import session as db_session
from ..email_renderer.engine import render_email_template
from ..models.email_task import EmailTask
from ..models.project import Project
from ..models.smtp_config import SmtpConfig
from ..services import smtp_service
from .events import SendEvent, event_bus
from .retry import schedule_retry_or_fail
from .sender import send_email
from .state import worker_state

logger = logging.getLogger(__name__)


async def check_rate_limit(db: AsyncSession, smtp_config_id) -> None:
    """检查近 1 小时发送量是否超出限制"""
    result = await db.execute(
        select(
            func.count(EmailTask.id).label("cnt"),
            SmtpConfig.max_per_hour,
        )
        .join(SmtpConfig, SmtpConfig.id == EmailTask.smtp_config_id)
        .where(
            EmailTask.smtp_config_id == smtp_config_id,
            EmailTask.status == "sent",
            EmailTask.sent_at >= func.now() - text("interval '1 hour'"),
        )
        .group_by(SmtpConfig.max_per_hour)
    )
    row = result.one_or_none()
    if row and row.cnt >= row.max_per_hour:
        raise Exception(f"超过每小时 {row.max_per_hour} 封限制")


async def fetch_next_task(db: AsyncSession) -> EmailTask | None:
    """使用 FOR UPDATE SKIP LOCKED 安全地抢占一个待处理任务"""
    now = func.now()
    subq = (
        select(EmailTask.id)
        .where(
            EmailTask.status.in_(["pending", "retry"]),
            or_(EmailTask.next_retry_at.is_(None), EmailTask.next_retry_at <= now),
            or_(EmailTask.scheduled_at.is_(None), EmailTask.scheduled_at <= now),
        )
        .order_by(EmailTask.priority.desc(), EmailTask.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    result = await db.execute(
        update(EmailTask)
        .where(EmailTask.id.in_(subq))
        .values(status="processing", processing_at=now)
        .returning(EmailTask)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def process_task(task_id) -> None:
    """处理单个发送任务"""
    worker_state.active_count += 1
    try:
        async with db_session.async_session_maker() as db:
            task = await db.get(EmailTask, task_id)
            if not task:
                return

            project = await db.get(Project, task.project_id)
            project_name = project.name if project else "unknown"

            try:
                # 获取 SMTP 配置
                smtp_config = None
                if task.smtp_config_id:
                    smtp_config = await db.get(SmtpConfig, task.smtp_config_id)
                if not smtp_config:
                    smtp_config = await smtp_service.get_default_config(db, task.project_id)
                if not smtp_config:
                    raise Exception("没有可用的 SMTP 配置")

                # 检查频率限制
                await check_rate_limit(db, smtp_config.id)

                # 渲染模板
                subject = task.subject
                body_html = task.body_html
                body_text = task.body_text
                if task.template_id:
                    subject, body_html, body_text = await render_email_template(
                        db, task.project_id, task.template_id, task.template_vars or {}
                    )

                # 发送邮件
                await send_email(
                    smtp_config,
                    task.to_addrs,
                    subject,
                    body_html=body_html,
                    body_text=body_text,
                    cc_addrs=task.cc_addrs,
                    bcc_addrs=task.bcc_addrs,
                    reply_to=task.reply_to,
                )

                # 标记成功
                task.status = "sent"
                task.sent_at = datetime.now(timezone.utc)
                task.error = None
                await db.commit()

                # 发布事件
                await event_bus.publish(SendEvent(
                    task_id=str(task.id),
                    project_name=project_name,
                    to=task.to_addrs[0] if task.to_addrs else "",
                    subject=subject,
                    status="sent",
                ))

                # Webhook 回调
                if task.webhook_url:
                    await _notify_webhook(task.webhook_url, str(task.id), "sent")

            except Exception as e:
                logger.error("发送失败 task=%s: %s", task.id, e)
                await schedule_retry_or_fail(db, task, str(e))

                await event_bus.publish(SendEvent(
                    task_id=str(task.id),
                    project_name=project_name,
                    to=task.to_addrs[0] if task.to_addrs else "",
                    subject=task.subject,
                    status="failed",
                    error=str(e),
                ))

                if task.webhook_url and task.status == "failed":
                    await _notify_webhook(task.webhook_url, str(task.id), "failed", str(e))

    finally:
        worker_state.active_count -= 1


async def worker_loop() -> None:
    """Worker 主循环"""
    import time

    worker_state.running = True
    worker_state.started_at = time.time()
    semaphore = asyncio.Semaphore(settings.worker_concurrency)

    logger.info("Worker 启动，并发数: %d", settings.worker_concurrency)

    while worker_state.running:
        async with semaphore:
            try:
                async with db_session.async_session_maker() as db:
                    task = await fetch_next_task(db)
                if task:
                    asyncio.create_task(process_task(task.id))
                else:
                    await asyncio.sleep(settings.worker_poll_interval)
            except Exception as e:
                logger.error("Worker 循环异常: %s", e)
                await asyncio.sleep(settings.worker_poll_interval)


async def _notify_webhook(url: str, task_id: str, status: str, error: str | None = None) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={
                "task_id": task_id,
                "status": status,
                "error": error,
            })
    except Exception as e:
        logger.warning("Webhook 回调失败 %s: %s", url, e)
