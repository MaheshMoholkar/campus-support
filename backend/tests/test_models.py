import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.enums import Role
from app.main import app as api
from app.models import WorkSession, utcnow
from tests.factories import make_ticket_row, make_user


def test_ticket_numbers_come_from_the_sequence(db):
    reporter = make_user(db, Role.REPORTER)

    first = make_ticket_row(db, reporter)
    second = make_ticket_row(db, reporter)

    assert re.fullmatch(r"CS-\d{6}", first.number)
    assert int(second.number[3:]) == int(first.number[3:]) + 1


def test_enum_columns_store_the_enum_value(db):
    ticket = make_ticket_row(db, make_user(db, Role.REPORTER))

    raw = db.execute(
        text("SELECT status FROM tickets WHERE id = :id"), {"id": ticket.id}
    ).scalar_one()

    assert raw == "pending_for_approval"


def test_only_one_open_work_session_per_ticket(db):
    developer = make_user(db, Role.DEVELOPER)
    ticket = make_ticket_row(db, make_user(db, Role.REPORTER))
    db.add(WorkSession(ticket_id=ticket.id, developer_id=developer.id, started_at=utcnow()))
    db.flush()

    db.add(WorkSession(ticket_id=ticket.id, developer_id=developer.id, started_at=utcnow()))

    with pytest.raises(IntegrityError):
        db.flush()


def test_tests_use_their_own_schema_not_the_development_tables(db):
    assert db.execute(text("SELECT current_schema()")).scalar_one() == "test"
    assert db.execute(text("SELECT to_regclass('test.tickets')")).scalar_one() is not None
    assert db.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_vector_extension_lives_in_public_so_dropping_the_test_schema_keeps_it(db):
    schema = db.execute(
        text(
            "SELECT n.nspname FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
        )
    ).scalar_one()

    assert schema == "public"


def test_database_routes_fail_loudly_without_the_client_fixture():
    # Without the fixture the app would open its own session on the development tables.
    with pytest.raises(RuntimeError, match="client fixture"):
        TestClient(api).post("/api/v1/auth/login", json={"email": "a@b.example", "password": "x"})
