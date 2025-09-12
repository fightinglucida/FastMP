from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MpAccount(Base):
    __tablename__ = "mp_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    biz: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("categories.id"), nullable=True)
    owner_email: Mapped[str] = mapped_column(String(255), ForeignKey("accounts.email"), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    article_account: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_mp_accounts_name_unique", "name", unique=True),
        Index("ix_mp_accounts_biz_unique", "biz", unique=True),
    )
