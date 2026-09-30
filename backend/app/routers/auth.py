from fastapi import APIRouter, HTTPException, Response

from app.core.config import settings
from app.core.deps import CurrentUser, DbDep
from app.core.security import COOKIE_NAME, create_session_token
from app.models import User
from app.schemas.auth import LoginIn, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: DbDep) -> User:
    user = users.authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user.id),
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
