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
    """处理单个发送任务（三阶段：加载 → 发送 → 更新）

    关键设计：SMTP 发送期间不持有 DB 连接。
    原因：aiosmtplib 握手/传输可能耗时数秒，若持有连接会耗尽连接池，
    导致同期 API 请求无法获取连接而超时。
    """
    worker_state.active_count += 1
    try:
        # ── 阶段一：从 DB 加载所有必要数据，然后立即释放连接 ──────────
        smtp_config: SmtpConfig | None = None
        to_addrs: list[str] = []
        cc_addrs: list[str] | None = None
        bcc_addrs: list[str] | None = None
        reply_to: str | None = None
        subject: str = ""
        body_html: str | None = None
        body_text: str | None = None
        project_name: str = "unknown"
        webhook_url: str | None = None
        phase1_error: str | None = None

        try:
            async with db_session.async_session_maker() as db:
                task = await db.get(EmailTask, task_id)
                if not task:
                    return

                project = await db.get(Project, task.project_id)
                project_name = project.name if project else "unknown"
                webhook_url = task.webhook_url
                subject = task.subject or ""
                to_addrs = list(task.to_addrs or [])
                cc_addrs = list(task.cc_addrs) if task.cc_addrs else None
                bcc_addrs = list(task.bcc_addrs) if task.bcc_addrs else None
                reply_to = task.reply_to

                if task.smtp_config_id:
                    cfg = await db.get(SmtpConfig, task.smtp_config_id)
                    if cfg and cfg.is_active:
                        smtp_config = cfg
                if not smtp_config:
                    smtp_config = await smtp_service.get_default_config(db, task.project_id)
                if not smtp_config:
                    raise Exception("没有可用的 SMTP 配置")

                await check_rate_limit(db, smtp_config.id)

                body_html = task.body_html
                body_text = task.body_text
                if task.template_id:
                    subject, body_html, body_text = await render_email_template(
                        db, task.project_id, task.template_id, task.template_vars or {}
                    )

                # expunge 使对象脱离 session，保留已加载的列属性，
                # 避免 session 关闭后访问属性时抛出 DetachedInstanceError
                db.expunge(smtp_config)
        except Exception as e:
            phase1_error = str(e)

        # ── DB 连接已释放 ────────────────────────────────────────────────

        to_addr = to_addrs[0] if to_addrs else ""

        # ── 阶段二：SMTP 发送（完全不持有 DB 连接）─────────────────────
        send_error = phase1_error
        if not send_error and smtp_config is not None:
            try:
                await send_email(
                    smtp_config,
                    to_addrs,
                    subject,
                    body_html=body_html,
                    body_text=body_text,
                    cc_addrs=cc_addrs,
                    bcc_addrs=bcc_addrs,
                    reply_to=reply_to,
                )
            except Exception as e:
                send_error = str(e)

        # ── 阶段三：重新获取 DB 连接，更新任务状态 ──────────────────────
        final_status = "failed"
        async with db_session.async_session_maker() as db:
            task = await db.get(EmailTask, task_id)
            if not task:
                return

            if send_error:
                logger.error("发送失败 task=%s: %s", task_id, send_error)
                await schedule_retry_or_fail(db, task, send_error)
                final_status = task.status
            else:
                task.status = "sent"
                task.sent_at = datetime.now(timezone.utc)
                task.error = None
                await db.commit()
                final_status = "sent"

        await event_bus.publish(SendEvent(
            task_id=str(task_id),
            project_name=project_name,
            to=to_addr,
            subject=subject,
            status=final_status,
            error=send_error,
        ))

        if webhook_url:
            if not send_error:
                await _notify_webhook(webhook_url, str(task_id), "sent")
            elif final_status == "failed":
                await _notify_webhook(webhook_url, str(task_id), "failed", send_error)

    finally:
        worker_state.active_count -= 1


async def worker_loop() -> None:
    """Worker 主循环"""
    import time

    worker_state.running = True
    worker_state.started_at = time.time()

    logger.info("Worker 启动，并发数: %d", settings.worker_concurrency)

    while worker_state.running:
        # 已达到并发上限时等待，避免无限抢占任务
        if worker_state.active_count >= settings.worker_concurrency:
            await asyncio.sleep(settings.worker_poll_interval)
            continue
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


def _is_safe_webhook_url(url: str) -> bool:
    """拒绝指向内网/本地地址的 Webhook URL，防止 SSRF 攻击"""
    import ipaddress
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # 拒绝 localhost 及常见内网域名
        if hostname in ("localhost", "::1"):
            return False
        # 尝试解析为 IP 并检查是否为私有/回环地址
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # hostname 是域名，继续
        return True
    except Exception:
        return False


async def _notify_webhook(url: str, task_id: str, status: str, error: str | None = None) -> None:
    if not _is_safe_webhook_url(url):
        logger.warning("Webhook URL 不安全，已跳过: %s", url)
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json={
                "task_id": task_id,
                "status": status,
                "error": error,
            })
    except Exception as e:
        logger.warning("Webhook 回调失败 %s: %s", url, e)
