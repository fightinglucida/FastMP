from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete, func, and_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.account import Account
from app.models.mp_account import MpAccount
from app.models.mp_article import MpArticle
from app.schemas.gzhaccount_admin_ops import (
    GzhAccountShowRequest,
    GzhAccountChangeRequest,
    GzhAccountDeleteRequest,
)
from app.schemas.gzhaccount import MpAccountOut
from app.schemas.gzhaccount_list import (
    AccountListQuery, AccountListResponse,
    ArticleListQuery, ArticleListResponse,
)


router = APIRouter(prefix="/gzhaccount", tags=["gzhaccount-admin"]) 


def _account_selector_stmt(payload: GzhAccountShowRequest | GzhAccountChangeRequest | GzhAccountDeleteRequest):
    if getattr(payload, "id", None):
        return select(MpAccount).where(MpAccount.id == payload.id)
    if getattr(payload, "name", None):
        return select(MpAccount).where(MpAccount.name == payload.name)
    if getattr(payload, "biz", None):
        return select(MpAccount).where(MpAccount.biz == payload.biz)
    raise ValueError("必须提供 id、name 或 biz 其中之一")


def _enforce_account_access(user: Account, acc: MpAccount | None) -> None:
    if user.role.name == "admin" or getattr(user.role, "value", None) == "admin":
        return
    if not acc:
        return
    if acc.owner_email != user.email:
        raise HTTPException(status_code=403, detail="Permission denied for this account")


@router.post("/show", response_model=MpAccountOut)
def gzh_account_show(payload: GzhAccountShowRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> MpAccountOut:
    stmt = _account_selector_stmt(payload)
    acc = db.scalar(stmt)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    _enforce_account_access(current, acc)
    return MpAccountOut.model_validate(acc)


@router.post("/change", response_model=MpAccountOut)
def gzh_account_change(payload: GzhAccountChangeRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> MpAccountOut:
    payload.ensure_selector()
    stmt = _account_selector_stmt(payload)
    acc = db.scalar(stmt)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    _enforce_account_access(current, acc)

    # id/name/biz 不可改，其它允许
    updatable = {
        "description": payload.description,
        "category_id": payload.category_id,
        "avatar_url": payload.avatar_url,
        "avatar": payload.avatar,
    }
    if payload.owner_email is not None:
        # 仅管理员可修改归属
        if not (current.role.name == "admin" or getattr(current.role, "value", None) == "admin"):
            raise HTTPException(status_code=403, detail="Only admin can change owner_email")
        updatable["owner_email"] = payload.owner_email

    for k, v in list(updatable.items()):
        if v is None:
            updatable.pop(k)
    for k, v in updatable.items():
        setattr(acc, k, v)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return MpAccountOut.model_validate(acc)


@router.post("/delete")
def gzh_account_delete(payload: GzhAccountDeleteRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> dict:
    payload.ensure_selector()
    stmt = _account_selector_stmt(payload)
    acc = db.scalar(stmt)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    _enforce_account_access(current, acc)

    # 先删文章
    db.query(MpArticle).filter(MpArticle.mp_account == acc.name).delete(synchronize_session=False)
    # 再删账号
    db.delete(acc)
    db.commit()
    return {"status": "ok", "deleted": acc.id}


@router.post("/list", response_model=AccountListResponse)
def gzh_account_list(payload: AccountListQuery, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> AccountListResponse:
    # 可按 name/biz 精确过滤；普通用户自动限定 owner_email；管理员可传 owner_email 明确过滤
    where = []
    if payload.name:
        where.append(MpAccount.name == payload.name)
    if payload.biz:
        where.append(MpAccount.biz == payload.biz)

    is_admin = current.role.name == "admin" or getattr(current.role, "value", None) == "admin"
    if is_admin:
        if payload.owner_email:
            where.append(MpAccount.owner_email == payload.owner_email)
    else:
        where.append(MpAccount.owner_email == current.email)

    stmt_items = select(MpAccount).where(and_(*where)) if where else select(MpAccount)
    stmt_items = stmt_items.order_by(MpAccount.create_time.desc()).offset(payload.offset).limit(payload.limit)
    items = db.scalars(stmt_items).all()

    stmt_total = select(func.count()).select_from(MpAccount)
    if where:
        stmt_total = stmt_total.where(and_(*where))
    total = int(db.scalar(stmt_total) or 0)

    return AccountListResponse(items=[MpAccountOut.model_validate(i) for i in items], total=total, offset=payload.offset, limit=payload.limit)
