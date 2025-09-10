from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, ActivationStatus, UserRole
from app.services.security import hash_password, verify_password, create_access_token


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # Registration
    def register(self, email: str, password: str) -> Account:
        # Check existing
        exists = self.db.scalar(select(Account).where(Account.email == email))
        if exists:
            raise ValueError("Email already registered")

        acc = Account(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.user,
            activation_status=ActivationStatus.pending,
            expired_time=None,
        )
        self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)
        return acc

    # Login
    def login(self, email: str, password: str) -> str:
        acc = self.db.scalar(select(Account).where(Account.email == email))
        if not acc or not verify_password(password, acc.password_hash):
            raise ValueError("Invalid email or password")

        # Note: 激活码与有效期的校验将用于访问受保护资源时进行。
        # Keep token compact: rely on subject (user id) only; fetch user details from DB when needed
        token = create_access_token(subject=acc.id)
        return token
