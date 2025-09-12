from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, and_, delete, update, func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.account import Account, UserRole
from app.models.mp_article import MpArticle
from app.models.mp_account import MpAccount
from app.schemas.gzhaccount import MpArticleOut
from app.schemas.gzharticle import GzhArticleChangeRequest
from app.schemas.gzhaccount_list import ArticleListQuery, ArticleListResponse

router = APIRouter(prefix="/gzharticle", tags=["gzharticle"]) 


def _article_selector_stmt(payload: GzhArticleChangeRequest):
    if payload.id:
        return select(MpArticle).where(MpArticle.id == payload.id)
    if payload.url:
        return select(MpArticle).where(MpArticle.url == payload.url)
    raise ValueError("必须提供 id 或 url 其中之一")


def _enforce_article_access(user: Account, article: MpArticle | None, db: Session) -> None:
    if user.role.name == "admin" or getattr(user.role, "value", None) == "admin":
        return
    # 普通用户：只允许操作自己的文章（通过 mp_account -> MpAccount.owner_email 校验）
    if not article:
        return
    acc = db.scalar(select(MpAccount).where(MpAccount.name == article.mp_account))
    if not acc or acc.owner_email != user.email:
        raise HTTPException(status_code=403, detail="Permission denied for this article")


@router.post("/show", response_model=MpArticleOut)
def gzh_article_show(payload: GzhArticleChangeRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> MpArticleOut:
    stmt = _article_selector_stmt(payload)
    obj = db.scalar(stmt)
    if not obj:
        raise HTTPException(status_code=404, detail="Article not found")
    _enforce_article_access(current, obj, db)
    return MpArticleOut.model_validate(obj)


@router.post("/change", response_model=MpArticleOut)
def gzh_article_change(payload: GzhArticleChangeRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> MpArticleOut:
    payload.ensure_selector()
    stmt = _article_selector_stmt(payload)
    obj = db.scalar(stmt)
    if not obj:
        raise HTTPException(status_code=404, detail="Article not found")
    _enforce_article_access(current, obj, db)

    # 不可修改 id/url
    updatable = {
        "title": payload.title,
        "cover_url": payload.cover_url,
        "publish_date": payload.publish_date,
        "item_show_type": payload.item_show_type,
        "mp_account": payload.mp_account,
    }
    # 清除 None，保留显式设置的值
    updatable = {k: v for k, v in updatable.items() if v is not None}

    # 如果改 mp_account，需要检查目标账号归属
    if "mp_account" in updatable and updatable["mp_account"] != obj.mp_account:
        target = db.scalar(select(MpAccount).where(MpAccount.name == updatable["mp_account"]))
        if not target:
            raise HTTPException(status_code=400, detail="Target account not found")
        if current.role.name != "admin" and getattr(current.role, "value", None) != "admin":
            if target.owner_email != current.email:
                raise HTTPException(status_code=403, detail="Cannot move article to account not owned by you")

    for k, v in updatable.items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return MpArticleOut.model_validate(obj)


@router.post("/delete")
def gzh_article_delete(payload: GzhArticleChangeRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> dict:
    payload.ensure_selector()
    stmt = _article_selector_stmt(payload)
    obj = db.scalar(stmt)
    if not obj:
        raise HTTPException(status_code=404, detail="Article not found")
    _enforce_article_access(current, obj, db)

    db.delete(obj)
    db.commit()
    return {"status": "ok", "deleted": obj.id}


@router.post("/list", response_model=ArticleListResponse)
def gzh_article_list(payload: ArticleListQuery, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> ArticleListResponse:
    # 过滤条件：mp_account/url/title_contains；管理员可传 owner_email 控制范围
    where = []
    if payload.mp_account:
        where.append(MpArticle.mp_account == payload.mp_account)
    if payload.url:
        where.append(MpArticle.url == payload.url)
    if payload.title_contains:
        from sqlalchemy import literal
        where.append(MpArticle.title.like(f"%{payload.title_contains}%"))

    is_admin = current.role.name == "admin" or getattr(current.role, "value", None) == "admin"
    if not is_admin:
        # 普通用户，仅限自己的账号文章
        sub = select(MpAccount.name).where(MpAccount.owner_email == current.email)
        where.append(MpArticle.mp_account.in_(sub))
    else:
        if payload.owner_email:
            sub = select(MpAccount.name).where(MpAccount.owner_email == payload.owner_email)
            where.append(MpArticle.mp_account.in_(sub))

    stmt_items = select(MpArticle)
    if where:
        from sqlalchemy import and_
        stmt_items = stmt_items.where(and_(*where))
    from sqlalchemy import desc
    stmt_items = stmt_items.order_by(desc(MpArticle.publish_date), desc(MpArticle.create_time)).offset(payload.offset).limit(payload.limit)
    items = db.scalars(stmt_items).all()

    stmt_total = select(func.count()).select_from(MpArticle)
    if where:
        from sqlalchemy import and_
        stmt_total = stmt_total.where(and_(*where))
    total = int(db.scalar(stmt_total) or 0)

    return ArticleListResponse(items=[MpArticleOut.model_validate(i) for i in items], total=total, offset=payload.offset, limit=payload.limit)
