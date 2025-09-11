from __future__ import annotations

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.account import Account
from app.schemas.cookie import (
    CookieChangeRequest,
    CookieDeleteRequest,
    CookieGetResponse,
    CookieListResponse,
    CookieOut,
)
from app.services.cookie import CookieService, WechatLoginResult

router = APIRouter(prefix="/cookie", tags=["cookie"])


@router.get("/get", response_model=CookieGetResponse)
def cookie_get(
    db: Session = Depends(get_db),
    current: Account = Depends(require_active_user),
    inline_qr: bool = Query(default=True, description="是否在响应中返回二维码base64"),
) -> CookieGetResponse:
    """
    非阻塞 immediate 模式：立即返回二维码和 login_key，不在接口中阻塞等待扫码。
    客户端随后使用 /cookie/poll?login_key=xxx 轮询状态。
    """
    svc = CookieService(db)
    result = svc.wechat_login_immediate_start()
    if result.status in ("pending", "failed"):
        return CookieGetResponse(
            status=result.status,
            message=result.message,
            qrcode_base64=result.qrcode_base64 if inline_qr else None,
            login_key=result.login_key,
        )
    # 理论上不会直接 success，这里兜底
    obj = svc.persist_login_for_user(owner_email=current.email, result=result)
    return CookieGetResponse(
        status="success",
        message="登录成功并保存cookie",
        qrcode_base64=result.qrcode_base64 if inline_qr else None,
        cookie=CookieOut.model_validate(obj),
    )


@router.post("/change", response_model=CookieOut)
def cookie_change(payload: CookieChangeRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> CookieOut:
    svc = CookieService(db)
    try:
        obj = svc.set_current_cookie(owner_email=current.email, token=payload.token)
        return CookieOut.model_validate(obj)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/delete")
def cookie_delete(payload: CookieDeleteRequest, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> dict:
    svc = CookieService(db)
    try:
        svc.delete_cookie(owner_email=current.email, token=payload.token)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/list", response_model=CookieListResponse)
def cookie_list(db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> CookieListResponse:
    svc = CookieService(db)
    items = svc.list_valid_cookies(owner_email=current.email)
    return CookieListResponse(items=[CookieOut.model_validate(i) for i in items])


@router.get("/poll", response_model=CookieGetResponse)
def cookie_poll(login_key: str, db: Session = Depends(get_db), current: Account = Depends(require_active_user)) -> CookieGetResponse:
    """轮询扫码状态（immediate 模式）。"""
    svc = CookieService(db)
    result: WechatLoginResult = svc.wechat_login_immediate_poll(login_key=login_key)
    if result.status == "success":
        obj = svc.persist_login_for_user(owner_email=current.email, result=result)
        return CookieGetResponse(
            status="success",
            message="登录成功并保存cookie",
            qrcode_base64=result.qrcode_base64,
            cookie=CookieOut.model_validate(obj),
        )
    elif result.status == "pending":
        return CookieGetResponse(
            status="pending",
            message=result.message,
            qrcode_base64=result.qrcode_base64,
        )
    else:
        raise HTTPException(status_code=400, detail=result.message)
