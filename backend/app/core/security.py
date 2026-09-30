from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

COOKIE_NAME = "cs_session"
_ALGORITHM = "HS256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError, InvalidHashError:
        return False


def create_session_token(user_id: int, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": issued,
        "exp": issued + timedelta(hours=settings.session_hours),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_ALGORITHM)


def read_session_token(token: str) -> int | None:
    """Return the user id, or None if the token is invalid or expired."""
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except jwt.PyJWTError, KeyError, ValueError:
        return None
