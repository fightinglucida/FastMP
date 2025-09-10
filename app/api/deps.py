from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.account import Account, ActivationStatus
from app.services.security import expand_uuid


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Account:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise credentials_exception
        # Backward-compatible: accept both full UUID and compact base64url
        user_id = sub
        if len(sub) <= 24 and all(c.isalnum() or c in "-_" for c in sub):
            try:
                user_id = expand_uuid(sub)
            except Exception:
                # If expansion fails, keep original
                user_id = sub
    except JWTError:
        raise credentials_exception

    user = db.get(Account, user_id)
    if user is None:
        raise credentials_exception
    return user


def require_active_user(current_user: Account = Depends(get_current_user)) -> Account:
    # 校验激活状态与有效期
    if current_user.activation_status != ActivationStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not activated")
    if current_user.expired_time is not None and current_user.expired_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Activation expired")
    return current_user
