from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field

from .gzhaccount import MpAccountOut, MpArticleOut


class AccountListQuery(BaseModel):
    # filters
    name: Optional[str] = Field(default=None, description="按 name 精确过滤")
    biz: Optional[str] = Field(default=None, description="按 biz 精确过滤")
    owner_email: Optional[str] = Field(default=None, description="管理员可传；普通用户忽略为当前用户")

    # pagination
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class AccountListResponse(BaseModel):
    items: List[MpAccountOut]
    total: int
    offset: int
    limit: int


class ArticleListQuery(BaseModel):
    # filters
    mp_account: Optional[str] = Field(default=None, description="按所属账号名称过滤（精确）")
    url: Optional[str] = Field(default=None, description="按 URL 精确过滤")
    title_contains: Optional[str] = Field(default=None, description="标题包含关键字（LIKE）")
    owner_email: Optional[str] = Field(default=None, description="管理员可传；普通用户忽略为当前用户")

    # pagination
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ArticleListResponse(BaseModel):
    items: List[MpArticleOut]
    total: int
    offset: int
    limit: int
