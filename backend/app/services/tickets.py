from datetime import UTC, datetime

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import FINAL_STATUSES, SIDE_STATUSES, Action, EventType, Role, Source, Status
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.models import ApprovalSection, ErpModule, Ticket, TicketEvent, User, ticket_number_seq
from app.schemas.tickets import (
    ActionBody,
    AttachmentOut,
    EventOut,
    TicketCreate,
    TicketDetail,
    TicketFilters,
    TicketOut,
)
from app.services import timer
from app.services.transitions import Actor, TicketState, allowed_actions, resolve

REMARK_REQUIRED = frozenset(
    {Action.APPROVE, Action.REJECT, Action.REQUEST_INFO, Action.REPLY, Action.CLOSE}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _actor(user: User) -> Actor:
    return Actor(user.id, user.role, user.approval_section_id)


def _state(ticket: Ticket) -> TicketState:
    return TicketState(
        ticket.status,
        ticket.previous_status,
        ticket.reporter_id,
        ticket.assignee_id,
        ticket.approval_section_id,
    )


def _record(
    db: Session,
    ticket: Ticket,
    actor: User,
    event_type: EventType,
    now: datetime,
    *,
    from_value: str | None = None,
    to_value: str | None = None,
    body: str | None = None,
    suggested_by: str | None = None,
) -> TicketEvent:
    event = TicketEvent(
        ticket_id=ticket.id,
        actor_id=actor.id,
        event_type=event_type,
        from_value=from_value,
        to_value=to_value,
        body=body,
        suggested_by=suggested_by,
        created_at=now,
    )
    db.add(event)
    return event


def can_view(actor: User, ticket: Ticket) -> bool:
    if actor.role is Role.REPORTER:
        return ticket.reporter_id == actor.id
    if actor.role is Role.APPROVER:
        return (
            ticket.approval_section_id is not None
            and ticket.approval_section_id == actor.approval_section_id
        )
    return True


def get_visible_ticket(db: Session, actor: User, ticket_id: int, *, lock: bool = False) -> Ticket:
    """Load a ticket the actor may see. With lock=True the row is locked until commit,
    so two simultaneous actions on one ticket run one after the other."""
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    ticket = db.execute(stmt).scalar_one_or_none()
    if ticket is None or not can_view(actor, ticket):
        raise NotFound("Ticket not found")
    return ticket


def create_ticket(
    db: Session, actor: User, data: TicketCreate, source: Source, now: datetime | None = None
) -> Ticket:
    """The single entry point for new tickets. The source decides the entry status."""
    now = now or _now()
    if source is Source.INTERNAL:
        if actor.role not in (Role.DEVELOPER, Role.LEAD):
            raise Forbidden("Only developers and the lead can raise internal tickets")
        section_id = None
        status = Status.WAITING_IN_QUEUE
    else:
        if actor.role is not Role.REPORTER:
            raise Forbidden("Only reporters can raise tickets")
        if (
            data.approval_section_id is None
            or db.get(ApprovalSection, data.approval_section_id) is None
        ):
            raise Invalid("Choose a valid approval section")
        section_id = data.approval_section_id
        status = Status.PENDING_APPROVAL
    if data.erp_module_id is not None and db.get(ErpModule, data.erp_module_id) is None:
        raise Invalid("Unknown ERP module")

    seq = db.execute(select(ticket_number_seq.next_value())).scalar_one()
    ticket = Ticket(
        number=f"CS-{seq:06d}",
        source=source,
        reporter_id=actor.id,
        institute_id=actor.institute_id,
        approval_section_id=section_id,
        ticket_for=data.ticket_for,
        ticket_type=data.ticket_type,
        erp_module_id=data.erp_module_id,
        page_url=data.page_url,
        description=data.description,
        contact_number=data.contact_number,
        extension=data.extension,
        status=status,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()
    _record(db, ticket, actor, EventType.CREATED, now, to_value=status.value)
    db.flush()
    return ticket


def _set_estimate(db: Session, actor: User, ticket: Ticket, minutes: int, now: datetime) -> None:
    if ticket.estimate_minutes == minutes:
        return
    old = ticket.estimate_minutes
    ticket.estimate_minutes = minutes
    _record(
        db,
        ticket,
        actor,
        EventType.ESTIMATE_CHANGE,
        now,
        from_value=None if old is None else str(old),
        to_value=str(minutes),
    )


def _assign(db: Session, actor: User, ticket: Ticket, body: ActionBody, now: datetime) -> None:
    developer = db.get(User, body.assignee_id) if body.assignee_id is not None else None
    if developer is None or developer.role is not Role.DEVELOPER or not developer.is_active:
        raise Invalid("assignee_id must be an active developer")
    previous = ticket.assignee_id
    if previous == developer.id:
        raise Conflict("Ticket is already assigned to this developer")
    ticket.assignee = developer
    _record(
        db,
        ticket,
        actor,
        EventType.ASSIGN if previous is None else EventType.REASSIGN,
        now,
        from_value=None if previous is None else str(previous),
        to_value=str(developer.id),
        suggested_by="lead",
    )
    if body.estimate_minutes is not None:
        _set_estimate(db, actor, ticket, body.estimate_minutes, now)


def apply_action(
    db: Session,
    actor: User,
    ticket_id: int,
    action: Action,
    body: ActionBody,
    now: datetime | None = None,
) -> Ticket:
    now = now or _now()
    ticket = get_visible_ticket(db, actor, ticket_id, lock=True)
    old_status = ticket.status
    new_status = resolve(_actor(actor), _state(ticket), action, body.side_status)
    if action in REMARK_REQUIRED and not body.remark:
        raise Invalid("A remark is required for this action")

    if action is Action.ASSIGN:
        _assign(db, actor, ticket, body, now)
    elif action is Action.SET_ESTIMATE:
        if body.estimate_minutes is None:
            raise Invalid("estimate_minutes is required")
        _set_estimate(db, actor, ticket, body.estimate_minutes, now)
    elif action in (Action.START, Action.RESUME):
        timer.start_timer(db, ticket.id, actor.id, now)
    elif action is Action.PAUSE:
        if not timer.stop_timer(db, ticket.id, now):
            raise Conflict("Timer is not running")

    if new_status != old_status:
        if old_status is Status.IN_PROCESS:
            timer.stop_timer(db, ticket.id, now)
        ticket.previous_status = old_status if new_status in SIDE_STATUSES else None
        if new_status is Status.CLOSED:
            ticket.closed_at = now
        ticket.status = new_status
        _record(
            db,
            ticket,
            actor,
            EventType.STATUS_CHANGE,
            now,
            from_value=old_status.value,
            to_value=new_status.value,
            body=body.remark,
        )
    ticket.updated_at = now
    db.flush()
    return ticket


def add_message(
    db: Session, actor: User, ticket_id: int, body: str, now: datetime | None = None
) -> TicketEvent:
    now = now or _now()
    ticket = get_visible_ticket(db, actor, ticket_id, lock=True)
    if ticket.status in FINAL_STATUSES:
        raise Conflict("This ticket is closed; no more messages can be added")
    event = _record(db, ticket, actor, EventType.MESSAGE, now, body=body)
    ticket.updated_at = now
    db.flush()
    return event


def latest_event(db: Session, ticket_id: int) -> TicketEvent:
    """The newest timeline entry of a ticket (the one an action just recorded)."""
    return db.execute(
        select(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.id.desc())
        .limit(1)
    ).scalar_one()


def bulk_assign(
    db: Session,
    actor: User,
    ticket_ids: list[int],
    assignee_id: int,
    estimate_minutes: int | None = None,
    now: datetime | None = None,
) -> list[Ticket]:
    """Assign many tickets. Any failure raises, and the request's rollback undoes all."""
    body = ActionBody(assignee_id=assignee_id, estimate_minutes=estimate_minutes)
    result: list[Ticket] = []
    for ticket_id in sorted(set(ticket_ids)):  # fixed order, so row locks cannot deadlock
        ticket = get_visible_ticket(db, actor, ticket_id, lock=True)
        if ticket.assignee_id == assignee_id:
            # Nothing to change, but still refuse tickets that cannot be assigned at all.
            resolve(_actor(actor), _state(ticket), Action.ASSIGN)
        else:
            ticket = apply_action(db, actor, ticket_id, Action.ASSIGN, body, now)
        result.append(ticket)
    return result


def list_tickets(db: Session, actor: User, filters: TicketFilters) -> tuple[list[Ticket], int]:
    stmt = select(Ticket)
    if actor.role is Role.REPORTER:
        stmt = stmt.where(Ticket.reporter_id == actor.id)
    elif actor.role is Role.APPROVER:
        if actor.approval_section_id is None:
            stmt = stmt.where(false())
        else:
            stmt = stmt.where(Ticket.approval_section_id == actor.approval_section_id)
    if filters.mine:
        owner = Ticket.assignee_id if actor.role is Role.DEVELOPER else Ticket.reporter_id
        stmt = stmt.where(owner == actor.id)
    for column, value in (
        (Ticket.institute_id, filters.institute_id),
        (Ticket.ticket_for, filters.ticket_for),
        (Ticket.ticket_type, filters.ticket_type),
        (Ticket.status, filters.status),
        (Ticket.assignee_id, filters.assignee_id),
    ):
        if value is not None:
            stmt = stmt.where(column == value)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.scalars(
        stmt.options(selectinload(Ticket.reporter), selectinload(Ticket.assignee))
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    )
    return list(rows), total


def ticket_detail(
    db: Session, actor: User, ticket: Ticket, now: datetime | None = None
) -> TicketDetail:
    now = now or _now()
    db.flush()
    db.refresh(ticket)  # reload columns and relationships changed earlier in the request
    return TicketDetail(
        **TicketOut.model_validate(ticket).model_dump(),
        contact_number=ticket.contact_number,
        extension=ticket.extension,
        events=[EventOut.model_validate(event) for event in ticket.events],
        attachments=[AttachmentOut.model_validate(a) for a in ticket.attachments],
        seconds_spent=timer.seconds_spent(db, ticket.id, now),
        timer_running=timer.open_session(db, ticket.id) is not None,
        allowed_actions=allowed_actions(_actor(actor), _state(ticket)),
    )
