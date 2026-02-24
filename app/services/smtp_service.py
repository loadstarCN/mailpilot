import uuid

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.security import CryptoService
from ..models.smtp_config import SmtpConfig

_crypto = CryptoService(settings.secret_key)


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
    from_email: str,
    from_name: str | None = None,
    max_per_hour: int = 100,
    is_default: bool = False,
) -> SmtpConfig:
    config = SmtpConfig(
        project_id=project_id,
        name=name,
        host=host,
        port=port,
        username=username,
        password=_crypto.encrypt(password),
        use_tls=use_tls,
        from_email=from_email,
        from_name=from_name,
        max_per_hour=max_per_hour,
        is_default=is_default,
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
    for key, value in kwargs.items():
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
        smtp = aiosmtplib.SMTP(
            hostname=config.host,
            port=config.port,
            use_tls=config.use_tls,
        )
        await smtp.connect()
        await smtp.login(config.username, password)
        await smtp.quit()
        return True, "连接成功"
    except Exception as e:
        return False, str(e)


def decrypt_password(encrypted: str) -> str:
    return _crypto.decrypt(encrypted)
