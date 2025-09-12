from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GzhSearchRequest(BaseModel):
    name: str = Field(min_length=1, description="公众号名称")
    max_articles: int = Field(default=0, ge=0, description="要抓取的文章数量，0 表示全量")


class MpAccountOut(BaseModel):
    id: str
    name: str
    biz: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    owner_email: str
    create_time: datetime
    update_time: Optional[datetime] = None
    avatar_url: Optional[str] = None
    avatar: Optional[str] = None
    article_account: int

    class Config:
        from_attributes = True


class MpArticleOut(BaseModel):
    id: str
    title: str
    url: str
    cover_url: Optional[str] = None
    publish_date: Optional[str] = None
    item_show_type: Optional[str] = None
    mp_account: str
    create_time: datetime

    class Config:
        from_attributes = True


class GzhSearchResponse(BaseModel):
    account: Optional[MpAccountOut] = None
    articles: List[MpArticleOut] = []


class GzhListRequest(BaseModel):
    name: str = Field(min_length=1)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)


class GzhListResponse(BaseModel):
    items: List[MpArticleOut]
    total: int
    name: str
    offset: int
    limit: int
