import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field, field_validator


class SendRequest(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=50)
    cc: list[EmailStr] | None = Field(None, max_length=50)
    bcc: list[EmailStr] | None = Field(None, max_length=50)
    reply_to: EmailStr | None = None
    subject: str = Field(min_length=1, max_length=500)
    body_html: str | None = Field(None, max_length=512000)
    body_text: str | None = Field(None, max_length=512000)
    priority: int = Field(0, ge=0, le=100)
    max_retries: int = Field(3, ge=0, le=10)
    smtp_config: str | None = None  # SMTP 配置的 UUID，不传则使用项目默认
    webhook_url: AnyHttpUrl | None = None
    scheduled_at: datetime | None = None

    @field_validator("webhook_url", mode="before")
    @classmethod
    def webhook_url_to_str(cls, v):
        return v  # 保留原始字符串，Pydantic 会验证格式


class SendTemplateRequest(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=50)
    cc: list[EmailStr] | None = Field(None, max_length=50)
    bcc: list[EmailStr] | None = Field(None, max_length=50)
    reply_to: EmailStr | None = None
    template: str
    variables: dict = {}
    priority: int = Field(0, ge=0, le=100)
    max_retries: int = Field(3, ge=0, le=10)
    smtp_config: str | None = None
    webhook_url: AnyHttpUrl | None = None
    scheduled_at: datetime | None = None


class SendResponse(BaseModel):
    task_id: uuid.UUID
    status: str = "pending"
