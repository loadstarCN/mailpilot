import uuid
from datetime import datetime, timedelta, timezone

import aiosmtplib
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.security import CryptoService
from ..models.email_task import EmailTask
from ..models.smtp_config import SmtpConfig


# 限流窗口：window → (SQL 时间间隔, 窗口时长, 提示文案)
_RATE_WINDOWS = {
    "hour": ("interval '1 hour'", timedelta(hours=1), "每小时"),
    "day": ("interval '24 hours'", timedelta(hours=24), "每天"),
}


class RateLimitExceeded(Exception):
    """SMTP 发送频率超限，携带限流窗口结束时间

    window 区分触发的是每小时（"hour"）还是每天（"day"）上限，limit 为该窗口的上限
    """

    def __init__(self, limit: int, retry_after: datetime, window: str = "hour"):
        self.limit = limit
        self.retry_after = retry_after
        self.window = window
        super().__init__(f"超过{_RATE_WINDOWS[window][2]} {limit} 封限制")


async def _count_sent_in_window(
    db: AsyncSession, smtp_config_id, interval: str
) -> tuple[int, datetime | None]:
    """统计窗口内该配置已发送（status='sent'）的数量及最早发送时间"""
    result = await db.execute(
        select(func.count(EmailTask.id), func.min(EmailTask.sent_at)).where(
            EmailTask.smtp_config_id == smtp_config_id,
            EmailTask.status == "sent",
            EmailTask.sent_at >= func.now() - text(interval),
        )
    )
    count, earliest = result.one()
    return count, earliest


async def check_rate_limit(db: AsyncSession, smtp_config_id) -> None:
    """检查近 1 小时 / 近 24 小时发送量是否超出限制，超限时抛出 RateLimitExceeded

    每天上限按滚动 24 小时计：任意 24 小时内不超，任何自然日也就不会超。
    两个窗口同时超限时，按结束更晚的窗口抛出（retry_after 取较晚者）。
    """
    config = await db.get(SmtpConfig, smtp_config_id)
    if not config:
        return
    limits = [("hour", config.max_per_hour)]
    if config.max_per_day:  # None / 0 表示不限
        limits.append(("day", config.max_per_day))

    exceeded: RateLimitExceeded | None = None
    for window, limit in limits:
        interval, duration, _ = _RATE_WINDOWS[window]
        count, earliest_sent_at = await _count_sent_in_window(db, smtp_config_id, interval)
        if not count or count < limit:
            continue
        # 窗口内最早一封移出窗口后才有空位
        retry_after = earliest_sent_at + duration + timedelta(seconds=5)
        # 确保 retry_after 带时区信息
        if retry_after.tzinfo is None:
            retry_after = retry_after.replace(tzinfo=timezone.utc)
        if exceeded is None or retry_after > exceeded.retry_after:
            exceeded = RateLimitExceeded(limit, retry_after, window)
    if exceeded:
        raise exceeded

_crypto = CryptoService(settings.secret_key)


async def _clear_project_defaults(
    db: AsyncSession,
    project_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """将同项目其他配置的 is_default 清为 False（排他性保证）"""
    stmt = update(SmtpConfig).where(
        SmtpConfig.project_id == project_id,
        SmtpConfig.is_default.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(SmtpConfig.id != exclude_id)
    await db.execute(stmt.values(is_default=False))


async def create_smtp_config(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    name: str | None,
    host: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool = True,
    use_ssl: bool = False,
    from_email: str,
    from_name: str | None = None,
    max_per_hour: int = 100,
    max_per_day: int | None = None,
    is_default: bool = False,
) -> SmtpConfig:
    if is_default:
        await _clear_project_defaults(db, project_id)
    config = SmtpConfig(
        project_id=project_id,
        name=name,
        host=host,
        port=port,
        username=username,
        password=_crypto.encrypt(password),
        use_tls=use_tls,
        use_ssl=use_ssl,
        from_email=from_email,
        from_name=from_name,
        max_per_hour=max_per_hour,
        max_per_day=max_per_day,
        is_default=is_default,
        is_active=True,  # 显式设置，避免 async ORM flush 前为 None 导致编辑页渲染错误
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def list_smtp_configs(
    db: AsyncSession, project_id: uuid.UUID | None = None
) -> list[SmtpConfig]:
    stmt = select(SmtpConfig).order_by(SmtpConfig.created_at.desc())
    if project_id:
        stmt = stmt.where(SmtpConfig.project_id == project_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_smtp_config(db: AsyncSession, config_id: uuid.UUID) -> SmtpConfig | None:
    return await db.get(SmtpConfig, config_id)


async def get_default_config(db: AsyncSession, project_id: uuid.UUID) -> SmtpConfig | None:
    result = await db.execute(
        select(SmtpConfig).where(
            SmtpConfig.project_id == project_id,
            SmtpConfig.is_default.is_(True),
            SmtpConfig.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def update_smtp_config(
    db: AsyncSession,
    config_id: uuid.UUID,
    **kwargs,
) -> SmtpConfig | None:
    config = await db.get(SmtpConfig, config_id)
    if not config:
        return None
    if "password" in kwargs and kwargs["password"]:
        kwargs["password"] = _crypto.encrypt(kwargs["password"])
    # is_default 设为 True 时，先清除同项目其他配置的默认标记
    if kwargs.get("is_default"):
        await _clear_project_defaults(db, config.project_id, exclude_id=config_id)
    for key, value in kwargs.items():
        # 布尔值（True/False）需直接设置；只跳过 None（表示"不修改此字段"）
        # max_per_day 例外：None 本身就是有效值（不限），显式传入即写入
        if value is not None or key == "max_per_day":
            setattr(config, key, value)
    await db.commit()
    await db.refresh(config)
    return config


async def delete_smtp_config(db: AsyncSession, config_id: uuid.UUID) -> bool:
    config = await db.get(SmtpConfig, config_id)
    if not config:
        return False
    await db.delete(config)
    await db.commit()
    return True


async def test_connection(db: AsyncSession, config_id: uuid.UUID) -> tuple[bool, str]:
    config = await db.get(SmtpConfig, config_id)
    if not config:
        return False, "配置不存在"
    try:
        password = _crypto.decrypt(config.password)
        # use_ssl=True → 隐式 SSL（端口 465）
        # use_tls=True → STARTTLS（端口 587）
        # 两者均 False → 明文
        smtp = aiosmtplib.SMTP(
            hostname=config.host,
            port=config.port,
            use_tls=config.use_ssl,
        )
        await smtp.connect()
        if config.use_tls and not config.use_ssl:
            await smtp.starttls()
        await smtp.login(config.username, password)
        await smtp.quit()
        return True, "连接成功"
    except Exception as e:
        return False, str(e)


def decrypt_password(encrypted: str) -> str:
    return _crypto.decrypt(encrypted)
