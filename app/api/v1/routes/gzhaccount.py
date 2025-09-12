from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.account import Account
from app.schemas.gzhaccount import (
    GzhSearchRequest,
    GzhSearchResponse,
    GzhListRequest,
    GzhListResponse,
    MpAccountOut,
    MpArticleOut,
)
from app.services.gzhaccount import GzhAccountService

router = APIRouter(prefix="/gzhaccount", tags=["gzhaccount"]) 


@router.post("/search", response_model=GzhSearchResponse)
def gzh_search(payload: GzhSearchRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> GzhSearchResponse:
    svc = GzhAccountService(db)
    try:
        acc, arts = svc.search_account(owner_email=current.email, name=payload.name, max_articles=payload.max_articles)
        return GzhSearchResponse(account=MpAccountOut.model_validate(acc) if acc else None, articles=[MpArticleOut.model_validate(a) for a in arts])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/search/stream")
def gzh_search_stream(payload: GzhSearchRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)):
    svc = GzhAccountService(db)

    def gen():
        import json
        try:
            for evt in svc.stream_search(owner_email=current.email, name=payload.name, max_articles=payload.max_articles):
                # 将 SQLAlchemy 对象转为 dict
                def mp_account_to_dict(a):
                    if not a:
                        return None
                    return {
                        "id": a.id,
                        "name": a.name,
                        "biz": a.biz,
                        "description": a.description,
                        "category_id": a.category_id,
                        "owner_email": a.owner_email,
                        "create_time": a.create_time.isoformat() if a.create_time else None,
                        "update_time": a.update_time.isoformat() if a.update_time else None,
                        "avatar_url": a.avatar_url,
                        "avatar": a.avatar,
                        "article_account": a.article_account,
                    }

                def mp_article_to_dict(x):
                    return {
                        "id": x.id,
                        "title": x.title,
                        "url": x.url,
                        "cover_url": x.cover_url,
                        "publish_date": x.publish_date,
                        "item_show_type": x.item_show_type,
                        "mp_account": x.mp_account,
                        "create_time": x.create_time.isoformat() if x.create_time else None,
                    }

                obj = dict(evt)
                if obj.get("account") and hasattr(obj["account"], "id"):
                    obj["account"] = mp_account_to_dict(obj["account"])
                if obj.get("items") and obj["items"] and hasattr(obj["items"][0], "id"):
                    obj["items"] = [mp_article_to_dict(i) for i in obj["items"]]
                yield json.dumps(obj, ensure_ascii=False) + "\n"
        except ValueError as e:
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.get("/list", response_model=GzhListResponse)
def gzh_list(name: str = Query(..., min_length=1), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> GzhListResponse:
    svc = GzhAccountService(db)
    try:
        items, total = svc.list_articles(owner_email=current.email, name=name, offset=offset, limit=limit)
        return GzhListResponse(items=[MpArticleOut.model_validate(i) for i in items], total=total, name=name, offset=offset, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
