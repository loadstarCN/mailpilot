import uuid

from jinja2 import BaseLoader, Environment, TemplateSyntaxError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.email_template import EmailTemplate


async def create_template(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    name: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    variables: list | None = None,
    description: str | None = None,
) -> EmailTemplate:
    template = EmailTemplate(
        project_id=project_id,
        name=name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        variables=variables or [],
        description=description,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_templates(
    db: AsyncSession, project_id: uuid.UUID | None = None, active_only: bool = False
) -> list[EmailTemplate]:
    stmt = select(EmailTemplate).order_by(EmailTemplate.created_at.desc())
    if project_id:
        stmt = stmt.where(EmailTemplate.project_id == project_id)
    if active_only:
        stmt = stmt.where(EmailTemplate.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> EmailTemplate | None:
    return await db.get(EmailTemplate, template_id)


async def get_template_by_name(
    db: AsyncSession, project_id: uuid.UUID, name: str, *, active_only: bool = True
) -> EmailTemplate | None:
    stmt = select(EmailTemplate).where(
        EmailTemplate.project_id == project_id,
        EmailTemplate.name == name,
    )
    if active_only:
        stmt = stmt.where(EmailTemplate.is_active.is_(True))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_template(
    db: AsyncSession, template_id: uuid.UUID, **kwargs
) -> EmailTemplate | None:
    template = await db.get(EmailTemplate, template_id)
    if not template:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template_id: uuid.UUID) -> bool:
    template = await db.get(EmailTemplate, template_id)
    if not template:
        return False
    await db.delete(template)
    await db.commit()
    return True


def render_preview(
    subject_tpl: str, body_html_tpl: str, body_text_tpl: str | None, variables: dict
) -> tuple[str, str, str | None]:
    env = Environment(loader=BaseLoader(), autoescape=True)
    subject = env.from_string(subject_tpl).render(**variables)
    body_html = env.from_string(body_html_tpl).render(**variables)
    body_text = None
    if body_text_tpl:
        body_text = env.from_string(body_text_tpl).render(**variables)
    return subject, body_html, body_text


def validate_template_syntax(content: str) -> tuple[bool, str]:
    env = Environment(loader=BaseLoader(), autoescape=True)
    try:
        env.parse(content)
        return True, ""
    except TemplateSyntaxError as e:
        return False, str(e)
