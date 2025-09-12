from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MpArticle(Base):
    __tablename__ = "mp_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    publish_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_show_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mp_account: Mapped[str] = mapped_column(String(255), ForeignKey("mp_accounts.name"), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_mp_articles_url_unique", "url", unique=True),
        Index("ix_mp_articles_account", "mp_account"),
    )
