from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CookieOut(BaseModel):
    id: str
    token: str
    owner_email: str
    created_time: datetime
    expire_time: datetime
    name: str
    avatar_url: Optional[str] = None
    avatar: Optional[str] = None
    local: str
    is_current: bool

    class Config:
        from_attributes = True


class CookieListResponse(BaseModel):
    items: List[CookieOut]


class CookieChangeRequest(BaseModel):
    token: str = Field(min_length=1)


class CookieDeleteRequest(BaseModel):
    token: str = Field(min_length=1)


class CookieGetResponse(BaseModel):
    # After QR scan flow
    status: str  # success | pending | failed
    message: str
    cookie: Optional[CookieOut] = None
    qrcode_base64: Optional[str] = None  # base64 image if requested
    login_key: Optional[str] = None  # immediate模式下返回的轮询key
