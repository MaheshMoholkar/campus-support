from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.models import WorkSession


def open_session(db: Session, ticket_id: int) -> WorkSession | None:
    return db.execute(
        select(WorkSession).where(
            WorkSession.ticket_id == ticket_id, WorkSession.stopped_at.is_(None)
        )
    ).scalar_one_or_none()


def start_timer(db: Session, ticket_id: int, developer_id: int, now: datetime) -> WorkSession:
    if open_session(db, ticket_id) is not None:
        raise Conflict("Timer is already running")
    session = WorkSession(ticket_id=ticket_id, developer_id=developer_id, started_at=now)
    db.add(session)
    db.flush()
    return session


def stop_timer(db: Session, ticket_id: int, now: datetime) -> bool:
    """Close the open segment. Returns False if the timer was not running."""
    session = open_session(db, ticket_id)
    if session is None:
        return False
    session.stopped_at = max(now, session.started_at)
    db.flush()
    return True


def seconds_spent(db: Session, ticket_id: int, now: datetime) -> int:
    sessions = db.scalars(select(WorkSession).where(WorkSession.ticket_id == ticket_id))
    return int(sum(((s.stopped_at or now) - s.started_at).total_seconds() for s in sessions))
