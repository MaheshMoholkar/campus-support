from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.core.security import COOKIE_NAME, create_session_token
from app.main import app as api
from app.models import User
from tests.factories import World, make_world

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


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def _get_db() -> Iterator[Session]:
        # Mirrors app.core.deps.get_db: a failed request rolls back its changes.
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    api.dependency_overrides[get_db] = _get_db
    yield TestClient(api)
    api.dependency_overrides.clear()


@pytest.fixture
def as_user(client: TestClient) -> Callable[[User], TestClient]:
    def _as(user: User) -> TestClient:
        logged_in = TestClient(api)
        logged_in.cookies.set(COOKIE_NAME, create_session_token(user.id))
        return logged_in

    return _as


@pytest.fixture
def world(db: Session) -> World:
    return make_world(db)
