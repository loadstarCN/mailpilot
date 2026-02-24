import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project


async def create_project(db: AsyncSession, name: str) -> Project:
    project = Project(
        name=name,
        api_key=secrets.token_hex(32),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession) -> list[Project]:
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    return await db.get(Project, project_id)


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, *, name: str | None = None, is_active: bool | None = None
) -> Project | None:
    project = await db.get(Project, project_id)
    if not project:
        return None
    if name is not None:
        project.name = name
    if is_active is not None:
        project.is_active = is_active
    await db.commit()
    await db.refresh(project)
    return project


async def regenerate_api_key(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    project = await db.get(Project, project_id)
    if not project:
        return None
    project.api_key = secrets.token_hex(32)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> bool:
    project = await db.get(Project, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True
