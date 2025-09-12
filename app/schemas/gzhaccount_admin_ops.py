from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from .gzhaccount import MpAccountOut


class GzhAccountShowRequest(BaseModel):
    # selector: id or name or biz
    id: Optional[str] = None
    name: Optional[str] = None
    biz: Optional[str] = None

    def ensure_selector(self) -> None:
        if not (self.id or self.name or self.biz):
            raise ValueError("必须提供 id、name 或 biz 其中之一用于查询")


class GzhAccountChangeRequest(BaseModel):
    # selector: id or name or biz
    id: Optional[str] = None
    name: Optional[str] = None
    biz: Optional[str] = None

    # updatable fields (id/name/biz 不可修改)
    description: Optional[str] = None
    category_id: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar: Optional[str] = None
    owner_email: Optional[str] = Field(default=None, description="仅管理员可修改归属人")

    def ensure_selector(self) -> None:
        if not (self.id or self.name or self.biz):
            raise ValueError("必须提供 id、name 或 biz 其中之一用于修改")


class GzhAccountDeleteRequest(BaseModel):
    # selector: id or name or biz
    id: Optional[str] = None
    name: Optional[str] = None
    biz: Optional[str] = None

    def ensure_selector(self) -> None:
        if not (self.id or self.name or self.biz):
            raise ValueError("必须提供 id、name 或 biz 其中之一用于删除")
