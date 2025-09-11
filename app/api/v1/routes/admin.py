from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_user
from app.models.account import Account, ActivationStatus, UserRole
from app.schemas.account import AccountOut
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserListResponse,
    AdminActivationCodeUpdate,
)
from app.services.admin import AdminUserService, AdminActivationCodeService

router = APIRouter(prefix="/admin", tags=["admin"])


# Users CRUD
@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin_user),
    email: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    activation_status: ActivationStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
):
    svc = AdminUserService(db)
    items, total = svc.list_users(email=email, role=role, activation_status=activation_status, page=page, size=size)
    return AdminUserListResponse(items=[AccountOut.model_validate(i) for i in items], total=total, page=page, size=size)


@router.get("/users/{user_id}", response_model=AccountOut)
def get_user(user_id: str, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminUserService(db)
    acc = svc.get_user(user_id)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AccountOut.model_validate(acc)


@router.post("/users", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminUserService(db)
    try:
        acc = svc.create_user(email=payload.email, password=payload.password, role=payload.role)
        return AccountOut.model_validate(acc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/users/{user_id}", response_model=AccountOut)
def update_user(user_id: str, payload: AdminUserUpdate, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminUserService(db)
    try:
        acc = svc.update_user(
            user_id=user_id,
            password=payload.password,
            role=payload.role,
            activation_status=payload.activation_status,
            expired_time=payload.expired_time,
        )
        return AccountOut.model_validate(acc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminUserService(db)
    try:
        svc.delete_user(user_id=user_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Activation code CRUD (extra admin endpoints)
@router.get("/activation/{code}")
def get_activation_code(code: str, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminActivationCodeService(db)
    ac = svc.get_code(code=code)
    if not ac:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code not found")
    from app.schemas.activation import ActivationCodeOut
    return ActivationCodeOut.model_validate(ac)


@router.put("/activation/{code}")
def update_activation_code(code: str, payload: AdminActivationCodeUpdate, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminActivationCodeService(db)
    try:
        ac = svc.update_code(code=code, valid_days=payload.valid_days, status=payload.status)
        from app.schemas.activation import ActivationCodeOut
        return ActivationCodeOut.model_validate(ac)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/activation/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activation_code(code: str, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = AdminActivationCodeService(db)
    try:
        svc.delete_code(code=code)
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
