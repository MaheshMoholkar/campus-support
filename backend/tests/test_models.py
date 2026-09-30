import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.enums import Role
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
