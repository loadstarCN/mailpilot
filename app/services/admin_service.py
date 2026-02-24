import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import hash_password, verify_password
from ..models.admin import Admin


async def authenticate(
    db: AsyncSession, username: str, password: str
) -> Admin | None:
    result = await db.execute(
        select(Admin).where(
            Admin.username == username,
            Admin.is_active.is_(True),
        )
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(password, admin.password_hash):
        return None
    admin.last_login_at = func.now()
    await db.commit()
    return admin


async def ensure_default_admin(
    db: AsyncSession, username: str, password: str
) -> None:
    result = await db.execute(select(func.count(Admin.id)))
    count = result.scalar() or 0
    if count == 0:
        admin = Admin(
            username=username,
            password_hash=hash_password(password),
        )
        db.add(admin)
        await db.commit()


async def change_password(
    db: AsyncSession, admin_id: uuid.UUID, old_password: str, new_password: str
) -> tuple[bool, str]:
    admin = await db.get(Admin, admin_id)
    if not admin:
        return False, "管理员不存在"
    if not verify_password(old_password, admin.password_hash):
        return False, "原密码错误"
    admin.password_hash = hash_password(new_password)
    await db.commit()
    return True, "密码已修改"
