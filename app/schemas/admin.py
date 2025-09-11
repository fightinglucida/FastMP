from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.account import ActivationStatus, UserRole
from app.schemas.account import AccountOut
from app.schemas.activation import ActivationCodeOut


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.user


class AdminUserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    role: Optional[UserRole] = None
    activation_status: Optional[ActivationStatus] = None
    expired_time: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    items: List[AccountOut]
    total: int
    page: int
    size: int


class AdminActivationCodeUpdate(BaseModel):
    valid_days: Optional[int] = Field(default=None, ge=1, le=3650)
    status: Optional[ActivationStatus] = None
