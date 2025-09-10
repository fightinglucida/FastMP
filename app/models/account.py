from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Enum as SAEnum, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class ActivationStatus(str, Enum):
    pending = "pending"
    active = "active"
    expired = "expired"
    revoked = "revoked"


class Account(Base):
    __tablename__ = "accounts"

    # 使用字符串存储 UUID，兼容多种数据库（PostgreSQL/SQLite）
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), default=UserRole.user, nullable=False)

    activation_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expired_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_status: Mapped[ActivationStatus] = mapped_column(
        SAEnum(ActivationStatus, name="activation_status"), default=ActivationStatus.pending, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_accounts_email_unique", "email", unique=True),
    )
