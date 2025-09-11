from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Cookie(Base):
    __tablename__ = "cookies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    # owner by email (FK to accounts.email)
    owner_email: Mapped[str] = mapped_column(String(255), ForeignKey("accounts.email"), index=True, nullable=False)

    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expire_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    avatar: Mapped[str] = mapped_column(String(1024), nullable=True)  # local path to avatar on server
    local: Mapped[str] = mapped_column(String(1024), nullable=False)  # folder path /static/cookies/<token>

    # Track which cookie is current for this owner
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_cookies_owner_is_current", "owner_email", "is_current"),
    )

    @staticmethod
    def default_expire_from_created(created: datetime) -> datetime:
        return created + timedelta(hours=88)
