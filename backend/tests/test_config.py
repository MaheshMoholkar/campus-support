import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "s" * 32


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_sqlalchemy_url_uses_psycopg_driver(scheme):
    settings = Settings(
        database_url=f"{scheme}u:p@db:5432/campus?sslmode=disable", session_secret=SECRET
    )

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@db:5432/campus?sslmode=disable"


def test_sqlalchemy_url_keeps_explicit_driver():
    url = "postgresql+psycopg://u:p@db:5432/campus"

    assert Settings(database_url=url, session_secret=SECRET).sqlalchemy_url == url


def test_session_secret_has_no_default(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)

    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://u:p@db/campus", _env_file=None)  # pyright: ignore[reportCallIssue]


def test_short_session_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql://u:p@db/campus", session_secret="too-short")
