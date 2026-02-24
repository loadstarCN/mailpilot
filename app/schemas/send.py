import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, HttpUrl


class SendRequest(BaseModel):
    to: list[EmailStr]
    cc: list[EmailStr] | None = None
    bcc: list[EmailStr] | None = None
    reply_to: EmailStr | None = None
    subject: str
    body_html: str | None = None
    body_text: str | None = None
    priority: int = 0
    max_retries: int = 3
    smtp_config: str | None = None  # name 或 id
    webhook_url: str | None = None
    scheduled_at: datetime | None = None


class SendTemplateRequest(BaseModel):
    to: list[EmailStr]
    cc: list[EmailStr] | None = None
    bcc: list[EmailStr] | None = None
    reply_to: EmailStr | None = None
    template: str
    variables: dict = {}
    priority: int = 0
    max_retries: int = 3
    smtp_config: str | None = None
    webhook_url: str | None = None
    scheduled_at: datetime | None = None


class SendResponse(BaseModel):
    task_id: uuid.UUID
    status: str = "pending"
