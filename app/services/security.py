from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Use PBKDF2-SHA256 for new hashes; keep bcrypt for backward compatibility
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# Compact UUID helpers: encode 16-byte UUID to 22-char base64url (no padding)

def compact_uuid(uuid_str: str) -> str:
    u = uuid.UUID(uuid_str)
    return base64.urlsafe_b64encode(u.bytes).rstrip(b"=").decode("ascii")


def expand_uuid(compact: str) -> str:
    pad = "=" * (-len(compact) % 4)
    raw = base64.urlsafe_b64decode(compact + pad)
    return str(uuid.UUID(bytes=raw))


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Keep payload minimal to shorten token
    to_encode: dict[str, Any] = {
        "sub": compact_uuid(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
