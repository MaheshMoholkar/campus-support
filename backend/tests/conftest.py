from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    admin = create_engine(settings.sqlalchemy_url)
    with admin.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS test CASCADE"))
        conn.execute(text("CREATE SCHEMA test"))
    admin.dispose()

    test_engine = create_engine(
        settings.sqlalchemy_url,
        connect_args={"options": "-csearch_path=test,public"},
    )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with test_engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose commits are savepoints inside a transaction that is rolled back."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
