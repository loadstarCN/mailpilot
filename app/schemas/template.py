import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    body_text: str | None = None
    variables: list[dict[str, Any]] | None = None
    description: str | None = None


class TemplateUpdate(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    variables: list[dict[str, Any]] | None = None
    description: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    subject: str
    body_html: str
    body_text: str | None
    variables: list | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class TemplatePreviewRequest(BaseModel):
    variables: dict = {}


class TemplatePreviewResponse(BaseModel):
    subject: str
    body_html: str
    body_text: str | None
