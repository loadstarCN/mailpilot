import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class SmtpConfigCreate(BaseModel):
    name: str | None = None
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    from_email: EmailStr
    from_name: str | None = None
    max_per_hour: int = 100
    is_default: bool = False


class SmtpConfigUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    use_tls: bool | None = None
    use_ssl: bool | None = None
    from_email: str | None = None
    from_name: str | None = None
    max_per_hour: int | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class SmtpConfigResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    host: str
    port: int
    username: str
    use_tls: bool
    use_ssl: bool
    from_email: str
    from_name: str | None
    max_per_hour: int
    is_default: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SmtpTestResponse(BaseModel):
    success: bool
    message: str
