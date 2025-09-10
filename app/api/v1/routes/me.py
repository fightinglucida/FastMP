from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.account import Account
from app.schemas.account import AccountOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AccountOut)
def read_me(current: Account = Depends(get_current_user)) -> AccountOut:
    return AccountOut.model_validate(current)
