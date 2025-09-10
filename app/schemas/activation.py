from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, EmailStr

from app.models.account import ActivationStatus


class GenerateCodesRequest(BaseModel):
    valid_days: int = Field(ge=1, le=3650, description="激活码激活后的有效天数")
    count: int = Field(ge=1, le=1000, description="生成的激活码数量")


class ActivationCodeOut(BaseModel):
    id: str
    activation_code: str
    valid_days: int
    activation_status: ActivationStatus
    user_email: Optional[EmailStr] = None
    expiry_date: Optional[str] = None
    activation_time: Optional[str] = None
    create_time: str
    update_time: str

    class Config:
        from_attributes = True


class GenerateCodesResponse(BaseModel):
    codes: List[ActivationCodeOut]


class ActivationCodeListResponse(BaseModel):
    items: List[ActivationCodeOut]
    total: int
    page: int
    size: int


class ActivateRequest(BaseModel):
    activation_code: str = Field(min_length=8, max_length=64)


class ActivateResponse(BaseModel):
    email: EmailStr
    activation_status: ActivationStatus
    expired_time: str


class RevokeRequest(BaseModel):
    activation_code: str = Field(min_length=8, max_length=64)
