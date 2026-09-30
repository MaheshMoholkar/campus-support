from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.enums import Role, Source, Status
from app.models import Ticket, User, WorkSession
from app.seed import seed
from app.services.users import authenticate
from tests.factories import make_user

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def test_seed_builds_the_demo_world(db):
    summary = seed(db, "demo-password", NOW)

    assert summary == {
        "institutes": 22,
        "sections": 6,
        "modules": 8,
        "users": 34,
        "tickets": 120,
    }
    statuses = set(db.scalars(select(Ticket.status)))
    assert {
        Status.PENDING_APPROVAL,
        Status.WAITING_IN_QUEUE,
        Status.IN_PROCESS,
        Status.CLOSED,
        Status.REJECTED,
        Status.CLARIFICATION_REQUIRED,
        Status.INSUFFICIENT_DATA,
    } <= statuses
    assert Source.INTERNAL in set(db.scalars(select(Ticket.source)))
    assert all(email.endswith("@tarangini.example") for email in db.scalars(select(User.email)))
    assert all(
        number is None or number.startswith("00000")
        for number in db.scalars(select(User.contact_number))
    )
    running = db.execute(
        select(func.count()).select_from(WorkSession).where(WorkSession.stopped_at.is_(None))
    ).scalar_one()
    assert running == 0
    assert authenticate(db, "lead@tarangini.example", "demo-password") is not None
    assert authenticate(db, "reporter22@tarangini.example", "demo-password") is not None


def test_seed_refuses_to_run_on_a_database_with_users(db):
    make_user(db, Role.ADMIN)

    with pytest.raises(SystemExit):
        seed(db, "demo-password", NOW)
