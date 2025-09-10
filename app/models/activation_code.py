from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.account import ActivationStatus


class ActivationCode(Base):
    __tablename__ = "activation_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    activation_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    # user_email references accounts.email
    user_email: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey("accounts.email"), nullable=True, index=True)

    activation_status: Mapped[ActivationStatus] = mapped_column(
        SAEnum(ActivationStatus, name="activation_status"), nullable=False, default=ActivationStatus.pending
    )

    # time fields stored as ISO string (text) per requirements
    expiry_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    activation_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False)
    create_time: Mapped[str] = mapped_column(String(64), nullable=False)
    update_time: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("ix_activation_codes_code_unique", "activation_code", unique=True),
    )
