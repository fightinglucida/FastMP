from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.account import AccountCreate, AccountOut
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def register(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountOut:
    svc = AuthService(db)
    try:
        acc = svc.register(email=payload.email, password=payload.password)
        return AccountOut.model_validate(acc)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    svc = AuthService(db)
    try:
        token = svc.login(email=payload.email, password=payload.password)
        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
