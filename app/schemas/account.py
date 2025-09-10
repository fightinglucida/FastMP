from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class ActivationStatus(str, Enum):
    pending = "pending"
    active = "active"
    expired = "expired"
    revoked = "revoked"


class AccountCreate(BaseModel):
    email: EmailStr = Field(description="用户邮箱，作为登录名")
    password: str = Field(min_length=6, max_length=128, description="登录密码")


class AccountOut(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    activation_status: ActivationStatus
    expired_time: Optional[datetime] = None

    class Config:
        from_attributes = True
