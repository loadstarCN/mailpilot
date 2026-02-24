import uuid

from jinja2 import BaseLoader, Environment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.email_template import EmailTemplate


class TemplateNotFound(Exception):
    pass


async def render_email_template(
    db: AsyncSession,
    project_id: uuid.UUID,
    template_name: str,
    variables: dict,
) -> tuple[str, str, str | None]:
    """渲染邮件模板，返回 (subject, body_html, body_text)"""
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.project_id == project_id,
            EmailTemplate.name == template_name,
            EmailTemplate.is_active.is_(True),
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise TemplateNotFound(f"模板 '{template_name}' 不存在")

    env = Environment(loader=BaseLoader(), autoescape=True)
    subject = env.from_string(template.subject).render(**variables)
    body_html = env.from_string(template.body_html).render(**variables)
    body_text = None
    if template.body_text:
        body_text = env.from_string(template.body_text).render(**variables)

    return subject, body_html, body_text
