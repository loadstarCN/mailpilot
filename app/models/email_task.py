import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, generate_uuid


class EmailTask(Base):
    __tablename__ = "email_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=generate_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    smtp_config_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("smtp_configs.id", ondelete="SET NULL")
    )
    to_addrs: Mapped[list[str]] = mapped_column(ARRAY(String))
    cc_addrs: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    bcc_addrs: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    reply_to: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[str | None] = mapped_column(String(100))
    template_vars: Mapped[dict | None] = mapped_column(JSONB)
    attachments: Mapped[list | None] = mapped_column(JSONB)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    error: Mapped[str | None] = mapped_column(Text)
    webhook_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    processing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project = relationship("Project", back_populates="email_tasks")
    smtp_config = relationship("SmtpConfig")

    __table_args__ = (
        Index(
            "idx_tasks_pending",
            priority.desc(),
            created_at.asc(),
            postgresql_where=(status.in_(["pending", "retry"])),
        ),
        Index(
            "idx_tasks_project_status",
            "project_id",
            "status",
            created_at.desc(),
        ),
    )
