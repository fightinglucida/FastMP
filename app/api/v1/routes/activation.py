from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.account import Account, UserRole, ActivationStatus
from app.models.activation_code import ActivationCode
from app.schemas.activation import (
    GenerateCodesRequest,
    GenerateCodesResponse,
    ActivationCodeOut,
    ActivationCodeListResponse,
    ActivateRequest,
    ActivateResponse,
    RevokeRequest,
)
from app.services.activation import ActivationService

router = APIRouter(prefix="/activation", tags=["activation"]) 


def require_admin_user(current_user: Account = Depends(get_current_user)) -> Account:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privilege required")
    return current_user


@router.post("/generate", response_model=GenerateCodesResponse)
def generate_codes(payload: GenerateCodesRequest, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = ActivationService(db)
    codes = svc.generate(valid_days=payload.valid_days, count=payload.count)
    return GenerateCodesResponse(codes=[ActivationCodeOut.model_validate(c) for c in codes])


@router.get("/list", response_model=ActivationCodeListResponse)
def list_codes(
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin_user),
    status: ActivationStatus | None = Query(default=None),
    email: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
):
    svc = ActivationService(db)
    items, total = svc.list_codes(status=status, user_email=email, page=page, size=size)
    return ActivationCodeListResponse(items=[ActivationCodeOut.model_validate(i) for i in items], total=total, page=page, size=size)


@router.post("/revoke", response_model=ActivationCodeOut)
def revoke_code(payload: RevokeRequest, db: Session = Depends(get_db), _: Account = Depends(require_admin_user)):
    svc = ActivationService(db)
    try:
        ac = svc.revoke(activation_code=payload.activation_code)
        return ActivationCodeOut.model_validate(ac)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/export", response_class=StreamingResponse)
def export_codes(
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin_user),
    status: ActivationStatus | None = Query(default=None),
    email: str | None = Query(default=None),
):
    # Stream CSV with header
    from io import StringIO
    import csv

    # Query all matched codes without pagination
    stmt = select(ActivationCode)
    if status is not None:
        stmt = stmt.where(ActivationCode.activation_status == status)
    if email is not None:
        stmt = stmt.where(ActivationCode.user_email == email)
    stmt = stmt.order_by(ActivationCode.create_time.desc())

    rows = db.scalars(stmt).all()

    def iter_csv():
        buffer = StringIO()
        writer = csv.writer(buffer)
        # header
        writer.writerow([
            "id",
            "activation_code",
            "user_email",
            "activation_status",
            "valid_days",
            "create_time",
            "update_time",
            "activation_time",
            "expiry_date",
        ])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        # rows
        for r in rows:
            writer.writerow([
                r.id,
                r.activation_code,
                r.user_email or "",
                r.activation_status.value,
                r.valid_days,
                r.create_time,
                r.update_time,
                r.activation_time or "",
                r.expiry_date or "",
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    headers = {"Content-Disposition": "attachment; filename=activation_codes.csv"}
    return StreamingResponse(iter_csv(), media_type="text/csv", headers=headers)


@router.post("/activate", response_model=ActivateResponse)
def activate_code(payload: ActivateRequest, db: Session = Depends(get_db), current_user: Account = Depends(get_current_user)):
    svc = ActivationService(db)
    try:
        account, ac = svc.activate(account=current_user, activation_code=payload.activation_code)
        return ActivateResponse(email=account.email, activation_status=account.activation_status, expired_time=account.expired_time.isoformat())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
