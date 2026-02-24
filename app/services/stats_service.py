import uuid

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.email_task import EmailTask
from ..models.project import Project
from ..models.smtp_config import SmtpConfig


async def get_overview(db: AsyncSession, project_id: uuid.UUID | None = None) -> dict:
    now = func.now()
    today_start = func.date_trunc("day", now)
    week_start = func.date_trunc("week", now)
    month_start = func.date_trunc("month", now)

    def _period_stats(start):
        return [
            func.count().filter(EmailTask.created_at >= start).label("total"),
            func.count().filter(
                EmailTask.created_at >= start, EmailTask.status == "sent"
            ).label("success"),
            func.count().filter(
                EmailTask.created_at >= start, EmailTask.status == "failed"
            ).label("failed"),
        ]

    stmt = select(
        *_period_stats(today_start),
        *[
            c.label(f"week_{c.name}" if hasattr(c, "name") else None)
            for c in _period_stats(week_start)
        ],
        *[
            c.label(f"month_{c.name}" if hasattr(c, "name") else None)
            for c in _period_stats(month_start)
        ],
    ).select_from(EmailTask)

    if project_id:
        stmt = stmt.where(EmailTask.project_id == project_id)

    # 简化实现：分别查询各时段
    results = {}
    for period_name, start in [("today", today_start), ("week", week_start), ("month", month_start)]:
        period_stmt = select(
            func.count().label("total"),
            func.count().filter(EmailTask.status == "sent").label("success"),
            func.count().filter(EmailTask.status == "failed").label("failed"),
        ).select_from(EmailTask).where(EmailTask.created_at >= start)

        if project_id:
            period_stmt = period_stmt.where(EmailTask.project_id == project_id)

        row = (await db.execute(period_stmt)).one()
        results[period_name] = {
            "total": row.total,
            "success": row.success,
            "failed": row.failed,
        }

    return results


async def get_trend(
    db: AsyncSession, period: str = "day", project_id: uuid.UUID | None = None
) -> list[dict]:
    if period == "day":
        trunc = func.date_trunc("hour", EmailTask.created_at)
        start_expr = func.now() - text("interval '24 hours'")
    elif period == "week":
        trunc = func.date_trunc("day", EmailTask.created_at)
        start_expr = func.now() - text("interval '7 days'")
    else:
        trunc = func.date_trunc("day", EmailTask.created_at)
        start_expr = func.now() - text("interval '30 days'")

    stmt = (
        select(
            trunc.label("time_bucket"),
            func.count().label("total"),
            func.count().filter(EmailTask.status == "sent").label("success"),
            func.count().filter(EmailTask.status == "failed").label("failed"),
        )
        .where(EmailTask.created_at >= start_expr)
        .group_by(text("1"))
        .order_by(text("1"))
    )
    if project_id:
        stmt = stmt.where(EmailTask.project_id == project_id)

    result = await db.execute(stmt)
    return [
        {
            "time_bucket": str(row.time_bucket),
            "total": row.total,
            "success": row.success,
            "failed": row.failed,
        }
        for row in result.all()
    ]


async def get_project_ranking(db: AsyncSession, limit: int = 10) -> list[dict]:
    stmt = (
        select(
            Project.name,
            func.count(EmailTask.id).label("total"),
            func.count().filter(EmailTask.status == "sent").label("success"),
        )
        .join(EmailTask, EmailTask.project_id == Project.id)
        .group_by(Project.id, Project.name)
        .order_by(text("2 DESC"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {"name": row.name, "total": row.total, "success": row.success}
        for row in result.all()
    ]


async def get_recent_failures(db: AsyncSession, limit: int = 20) -> list[EmailTask]:
    stmt = (
        select(EmailTask)
        .where(EmailTask.status == "failed")
        .order_by(EmailTask.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_queue_depth(db: AsyncSession) -> dict[str, int]:
    stmt = (
        select(EmailTask.status, func.count().label("count"))
        .group_by(EmailTask.status)
    )
    result = await db.execute(stmt)
    return {row.status: row.count for row in result.all()}


async def get_smtp_health(db: AsyncSession) -> list[dict]:
    """各 SMTP 配置最近 100 封邮件的成功/失败率"""
    stmt = (
        select(
            SmtpConfig.id,
            SmtpConfig.name,
            SmtpConfig.host,
            SmtpConfig.from_email,
            func.count(EmailTask.id).label("total"),
            func.count().filter(EmailTask.status == "sent").label("success"),
            func.count().filter(EmailTask.status == "failed").label("failed"),
        )
        .outerjoin(EmailTask, EmailTask.smtp_config_id == SmtpConfig.id)
        .where(SmtpConfig.is_active.is_(True))
        .group_by(SmtpConfig.id, SmtpConfig.name, SmtpConfig.host, SmtpConfig.from_email)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": str(row.id),
            "name": row.name or row.host,
            "host": row.host,
            "from_email": row.from_email,
            "total": row.total,
            "success": row.success,
            "failed": row.failed,
            "success_rate": round(row.success / row.total * 100, 1) if row.total > 0 else 0,
        }
        for row in result.all()
    ]
