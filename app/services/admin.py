from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account, ActivationStatus, UserRole
from app.models.activation_code import ActivationCode
from app.services.security import hash_password


class AdminUserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(
        self,
        *,
        email: Optional[str] = None,
        role: Optional[UserRole] = None,
        activation_status: Optional[ActivationStatus] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[list[Account], int]:
        from sqlalchemy import func

        stmt = select(Account)
        count_stmt = select(func.count()).select_from(Account)

        if email:
            # simple contains filter
            pattern = f"%{email}%"
            stmt = stmt.where(Account.email.ilike(pattern))
            count_stmt = count_stmt.where(Account.email.ilike(pattern))
        if role is not None:
            stmt = stmt.where(Account.role == role)
            count_stmt = count_stmt.where(Account.role == role)
        if activation_status is not None:
            stmt = stmt.where(Account.activation_status == activation_status)
            count_stmt = count_stmt.where(Account.activation_status == activation_status)

        stmt = stmt.order_by(Account.created_at.desc())
        total = self.db.scalar(count_stmt) or 0
        items = self.db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        return items, int(total)

    def get_user(self, user_id: str) -> Optional[Account]:
        return self.db.get(Account, user_id)

    def create_user(self, *, email: str, password: str, role: UserRole = UserRole.user) -> Account:
        if self.db.scalar(select(Account).where(Account.email == email)):
            raise ValueError("Email already exists")
        acc = Account(
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)
        return acc

    def update_user(
        self,
        *,
        user_id: str,
        password: Optional[str] = None,
        role: Optional[UserRole] = None,
        activation_status: Optional[ActivationStatus] = None,
        expired_time: Optional[datetime] = None,
    ) -> Account:
        acc = self.get_user(user_id)
        if not acc:
            raise ValueError("User not found")
        if password:
            acc.password_hash = hash_password(password)
        if role is not None:
            acc.role = role
        if activation_status is not None:
            acc.activation_status = activation_status
        if expired_time is not None:
            acc.expired_time = expired_time
        self.db.add(acc)
        self.db.commit()
        self.db.refresh(acc)
        return acc

    def delete_user(self, *, user_id: str) -> None:
        acc = self.get_user(user_id)
        if not acc:
            raise ValueError("User not found")
        # delete associated activation codes
        if acc.email:
            for ac in self.db.scalars(select(ActivationCode).where(ActivationCode.user_email == acc.email)).all():
                self.db.delete(ac)
        self.db.delete(acc)
        self.db.commit()


class AdminActivationCodeService:
    def __init__(self, db: Session):
        self.db = db

    def get_code(self, *, code: str) -> Optional[ActivationCode]:
        return self.db.scalar(select(ActivationCode).where(ActivationCode.activation_code == code))

    def update_code(self, *, code: str, valid_days: Optional[int] = None, status: Optional[ActivationStatus] = None) -> ActivationCode:
        ac = self.get_code(code=code)
        if not ac:
            raise ValueError("Activation code not found")
        if valid_days is not None:
            ac.valid_days = valid_days
        if status is not None:
            ac.activation_status = status
        ac.update_time = datetime.now(timezone.utc).isoformat()
        self.db.add(ac)
        self.db.commit()
        self.db.refresh(ac)
        return ac

    def delete_code(self, *, code: str) -> None:
        ac = self.get_code(code=code)
        if not ac:
            raise ValueError("Activation code not found")
        # If this code is linked to an account, reset that account's activation fields
        if ac.user_email:
            acc = self.db.scalar(select(Account).where(Account.email == ac.user_email))
            if acc and acc.activation_code == ac.activation_code:
                acc.activation_code = None
                acc.activation_status = ActivationStatus.pending
                acc.expired_time = None
                self.db.add(acc)
        self.db.delete(ac)
        self.db.commit()
