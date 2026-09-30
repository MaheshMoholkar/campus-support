from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.enums import Role
from app.core.security import read_session_token
from app.models import User
from app.services.storage import S3Storage, Storage


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbDep = Annotated[Session, Depends(get_db)]


def current_user(db: DbDep, cs_session: Annotated[str | None, Cookie()] = None) -> User:
    user_id = read_session_token(cs_session) if cs_session else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Not allowed for your role")
        return user

    return checker


@lru_cache
def _s3_storage() -> S3Storage:
    return S3Storage(settings)


def get_storage() -> Storage:
    return _s3_storage()


StorageDep = Annotated[Storage, Depends(get_storage)]
