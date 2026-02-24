import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, generate_uuid


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100))
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    smtp_configs = relationship(
        "SmtpConfig", back_populates="project", cascade="all, delete-orphan"
    )
    email_tasks = relationship(
        "EmailTask", back_populates="project", cascade="all, delete-orphan"
    )
    email_templates = relationship(
        "EmailTemplate", back_populates="project", cascade="all, delete-orphan"
    )
