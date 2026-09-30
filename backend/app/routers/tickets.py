from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbDep, StorageDep, require_roles
from app.core.enums import Action, Role, Source
from app.core.errors import Invalid
from app.models import User
from app.schemas.tickets import (
    ActionBody,
    BulkAssign,
    MessageCreate,
    TicketCreate,
    TicketDetail,
    TicketFilters,
    TicketOut,
    TicketPage,
)
from app.services import attachments, tickets

router = APIRouter(prefix="/tickets", tags=["tickets"])

LeadUser = Annotated[User, Depends(require_roles(Role.LEAD))]


@router.post("", response_model=TicketDetail, status_code=201)
def create_ticket(
    data: TicketCreate, db: DbDep, storage: StorageDep, user: CurrentUser
) -> TicketDetail:
    source = Source.INTERNAL if user.role in (Role.DEVELOPER, Role.LEAD) else Source.WEB
    ticket = tickets.create_ticket(db, user, data, source)
    attachments.attach(db, storage, user, ticket, data.attachment_keys)
    db.commit()
    return tickets.ticket_detail(db, user, ticket)


@router.get("", response_model=TicketPage)
def list_tickets(
    filters: Annotated[TicketFilters, Query()], db: DbDep, user: CurrentUser
) -> TicketPage:
    items, total = tickets.list_tickets(db, user, filters)
    return TicketPage(items=[TicketOut.model_validate(item) for item in items], total=total)


@router.post("/bulk-assign", response_model=list[TicketOut])
def bulk_assign(data: BulkAssign, db: DbDep, user: LeadUser) -> list[TicketOut]:
    assigned = tickets.bulk_assign(
        db, user, data.ticket_ids, data.assignee_id, data.estimate_minutes
    )
    db.commit()
    return [TicketOut.model_validate(ticket) for ticket in assigned]


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, db: DbDep, user: CurrentUser) -> TicketDetail:
    ticket = tickets.get_visible_ticket(db, user, ticket_id)
    return tickets.ticket_detail(db, user, ticket)


@router.post("/{ticket_id}/actions/{action}", response_model=TicketDetail)
def apply_action(
    ticket_id: int,
    action: Action,
    body: ActionBody,
    db: DbDep,
    storage: StorageDep,
    user: CurrentUser,
) -> TicketDetail:
    if body.attachment_keys and action is not Action.REPLY:
        raise Invalid("Attachments can be sent with a reply or a message only")
    ticket = tickets.apply_action(db, user, ticket_id, action, body)
    if body.attachment_keys:
        event = tickets.latest_event(db, ticket.id)
        attachments.attach(db, storage, user, ticket, body.attachment_keys, event)
    db.commit()
    return tickets.ticket_detail(db, user, ticket)


@router.post("/{ticket_id}/messages", response_model=TicketDetail, status_code=201)
def add_message(
    ticket_id: int, data: MessageCreate, db: DbDep, storage: StorageDep, user: CurrentUser
) -> TicketDetail:
    event = tickets.add_message(db, user, ticket_id, data.body)
    ticket = tickets.get_visible_ticket(db, user, ticket_id)
    attachments.attach(db, storage, user, ticket, data.attachment_keys, event)
    db.commit()
    return tickets.ticket_detail(db, user, ticket)
