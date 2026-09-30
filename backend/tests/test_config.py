import pytest

from app.core.config import Settings


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_sqlalchemy_url_uses_psycopg_driver(scheme):
    settings = Settings(database_url=f"{scheme}u:p@db:5432/campus?sslmode=disable")

    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@db:5432/campus?sslmode=disable"


def test_sqlalchemy_url_keeps_explicit_driver():
    url = "postgresql+psycopg://u:p@db:5432/campus"

    assert Settings(database_url=url).sqlalchemy_url == url
