from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activation_code import ActivationCode
from app.models.account import Account, ActivationStatus


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActivationService:
    def __init__(self, db: Session):
        self.db = db

    def generate(self, *, valid_days: int, count: int) -> List[ActivationCode]:
        out: List[ActivationCode] = []
        for _ in range(count):
            code = secrets.token_hex(16)  # 32-char hex
            ac = ActivationCode(
                id=str(uuid.uuid4()),
                activation_code=code,
                user_email=None,
                activation_status=ActivationStatus.pending,
                expiry_date=None,
                activation_time=None,
                valid_days=valid_days,
                create_time=now_iso(),
                update_time=now_iso(),
            )
            self.db.add(ac)
            out.append(ac)
        self.db.commit()
        for ac in out:
            self.db.refresh(ac)
        return out

    def list_codes(
        self,
        *,
        status: ActivationStatus | None = None,
        user_email: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[ActivationCode], int]:
        from sqlalchemy import func

        stmt = select(ActivationCode)
        count_stmt = select(func.count()).select_from(ActivationCode)
        if status is not None:
            stmt = stmt.where(ActivationCode.activation_status == status)
            count_stmt = count_stmt.where(ActivationCode.activation_status == status)
        if user_email is not None:
            stmt = stmt.where(ActivationCode.user_email == user_email)
            count_stmt = count_stmt.where(ActivationCode.user_email == user_email)

        # Order by create_time desc (ISO string order is ok)
        stmt = stmt.order_by(ActivationCode.create_time.desc())
        total = self.db.scalar(count_stmt) or 0
        items = self.db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
        return items, int(total)

    def revoke(self, *, activation_code: str) -> ActivationCode:
        ac = self.db.scalar(select(ActivationCode).where(ActivationCode.activation_code == activation_code))
        if not ac:
            raise ValueError("Activation code not found")
        ac.activation_status = ActivationStatus.revoked
        ac.update_time = now_iso()
        self.db.add(ac)
        self.db.commit()
        self.db.refresh(ac)
        return ac

    def activate(self, *, account: Account, activation_code: str) -> tuple[Account, ActivationCode]:
        ac = self.db.scalar(select(ActivationCode).where(ActivationCode.activation_code == activation_code))
        if not ac:
            raise ValueError("Activation code not found")
        if ac.activation_status != ActivationStatus.pending:
            raise ValueError("Activation code is not pending")

        # Compute expiry for account
        now = datetime.now(timezone.utc)
        expire_at = now + timedelta(days=ac.valid_days)

        # Update account
        account.activation_code = ac.activation_code
        account.activation_status = ActivationStatus.active
        account.expired_time = expire_at

        # Update activation code record
        ac.user_email = account.email
        ac.activation_status = ActivationStatus.active
        ac.expiry_date = expire_at.isoformat()
        ac.activation_time = now.isoformat()
        ac.update_time = now_iso()

        self.db.add(account)
        self.db.add(ac)
        self.db.commit()
        self.db.refresh(account)
        self.db.refresh(ac)
        return account, ac
