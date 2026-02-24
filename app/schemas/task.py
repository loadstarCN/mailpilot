import uuid
from datetime import datetime

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    to_addrs: list[str]
    cc_addrs: list[str] | None
    bcc_addrs: list[str] | None
    subject: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    error: str | None
    created_at: datetime
    scheduled_at: datetime | None
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
