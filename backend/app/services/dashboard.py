from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.enums import FINAL_STATUSES, EventType, Status
from app.models import Institute, Ticket, TicketEvent, User
from app.schemas.dashboard import Count, DashboardOut


def _counts(db: Session, stmt: Select) -> list[Count]:
    rows = db.execute(stmt).all()
    return sorted(
        (Count(label=str(getattr(label, "value", label)), count=count) for label, count in rows),
        key=lambda row: (-row.count, row.label),
    )


def dashboard(db: Session) -> DashboardOut:
    queued_at = (
        select(TicketEvent.ticket_id, func.min(TicketEvent.created_at).label("queued_at"))
        .where(
            TicketEvent.event_type.in_([EventType.CREATED, EventType.STATUS_CHANGE]),
            TicketEvent.to_value == Status.WAITING_IN_QUEUE.value,
        )
        .group_by(TicketEvent.ticket_id)
        .subquery()
    )
    avg_seconds = db.execute(
        select(func.avg(func.extract("epoch", Ticket.closed_at - queued_at.c.queued_at)))
        .join(queued_at, queued_at.c.ticket_id == Ticket.id)
        .where(Ticket.status == Status.CLOSED)
    ).scalar_one()

    return DashboardOut(
        by_status=_counts(db, select(Ticket.status, func.count()).group_by(Ticket.status)),
        by_ticket_for=_counts(
            db, select(Ticket.ticket_for, func.count()).group_by(Ticket.ticket_for)
        ),
        by_institute=_counts(
            db,
            select(Institute.name, func.count())
            .join(Ticket, Ticket.institute_id == Institute.id)
            .group_by(Institute.id, Institute.name),
        ),
        open_per_developer=_counts(
            db,
            select(User.name, func.count())
            .join(Ticket, Ticket.assignee_id == User.id)
            .where(Ticket.status.not_in(FINAL_STATUSES))
            .group_by(User.id, User.name),
        ),
        avg_hours_queue_to_close=(
            None if avg_seconds is None else round(float(avg_seconds) / 3600, 2)
        ),
    )
