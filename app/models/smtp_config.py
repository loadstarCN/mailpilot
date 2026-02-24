import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, generate_uuid


class SmtpConfig(Base):
    __tablename__ = "smtp_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=generate_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str | None] = mapped_column(String(100))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=587)
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(500))  # Fernet 加密存储
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True)   # STARTTLS（端口 587）
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)  # SSL（端口 465）
    from_email: Mapped[str] = mapped_column(String(255))
    from_name: Mapped[str | None] = mapped_column(String(100))
    max_per_hour: Mapped[int] = mapped_column(Integer, default=100)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project = relationship("Project", back_populates="smtp_configs")
