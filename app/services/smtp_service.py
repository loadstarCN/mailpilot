import uuid
from datetime import datetime, timedelta, timezone

import aiosmtplib
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.security import CryptoService
from ..models.email_task import EmailTask
from ..models.smtp_config import SmtpConfig


class RateLimitExceeded(Exception):
    """SMTP 发送频率超限，携带限流窗口结束时间"""

    def __init__(self, max_per_hour: int, retry_after: datetime):
        self.max_per_hour = max_per_hour
        self.retry_after = retry_after
        super().__init__(f"超过每小时 {max_per_hour} 封限制")


async def check_rate_limit(db: AsyncSession, smtp_config_id) -> None:
    """检查近 1 小时发送量是否超出限制，超限时抛出 RateLimitExceeded"""
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
        # 查询窗口内最早的 sent_at，计算限流窗口结束时间
        earliest = await db.execute(
            select(EmailTask.sent_at)
            .where(
                EmailTask.smtp_config_id == smtp_config_id,
                EmailTask.status == "sent",
                EmailTask.sent_at >= func.now() - text("interval '1 hour'"),
            )
            .order_by(EmailTask.sent_at.asc())
            .limit(1)
        )
        earliest_sent_at = earliest.scalar_one()
        retry_after = earliest_sent_at + timedelta(hours=1, seconds=5)
        # 确保 retry_after 带时区信息
        if retry_after.tzinfo is None:
            retry_after = retry_after.replace(tzinfo=timezone.utc)
        raise RateLimitExceeded(row.max_per_hour, retry_after)

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
        if value is not None:
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
