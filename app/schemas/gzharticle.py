from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from .gzhaccount import MpArticleOut


class GzhArticleChangeRequest(BaseModel):
    # Selector (one of)
    id: Optional[str] = Field(default=None, description="文章ID，用于定位记录（与 url 二选一）")
    url: Optional[str] = Field(default=None, description="文章URL（唯一），用于定位记录（与 id 二选一）")

    # Updatable fields (id/url 不可修改)
    title: Optional[str] = None
    cover_url: Optional[str] = None
    publish_date: Optional[str] = None
    item_show_type: Optional[int] = None
    mp_account: Optional[str] = Field(default=None, description="归属公众号名称（可改，需权限校验）")

    def ensure_selector(self) -> None:
        if not self.id and not self.url:
            raise ValueError("必须提供 id 或 url 作为定位字段")
