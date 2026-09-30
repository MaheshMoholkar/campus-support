from datetime import UTC, datetime, timedelta

from app.core.enums import Action, Source
from app.schemas.tickets import ActionBody, TicketCreate
from app.services import tickets
from app.services.dashboard import dashboard
from tests.factories import ticket_values

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def act(db, actor, ticket, action, minutes, **body):
    tickets.apply_action(db, actor, ticket.id, action, ActionBody.model_validate(body), at(minutes))


def closed_ticket(db, w, approved_at: int, closed_at: int):
    data = TicketCreate.model_validate(ticket_values(w))
    ticket = tickets.create_ticket(db, w.reporter, data, Source.WEB, at(0))
    act(db, w.approver, ticket, Action.APPROVE, approved_at, remark="Approved")
    act(db, w.lead, ticket, Action.ASSIGN, approved_at + 1, assignee_id=w.dev.id)
    act(db, w.dev, ticket, Action.START, approved_at + 2)
    act(db, w.dev, ticket, Action.CLOSE, closed_at, remark="Done")
    return ticket


def counts(rows) -> dict[str, int]:
    return {row.label: row.count for row in rows}


def test_dashboard_counts_and_average(db, world):
    w = world
    closed_ticket(db, w, approved_at=10, closed_at=70)  # 1 hour
    closed_ticket(db, w, approved_at=10, closed_at=190)  # 3 hours
    pending = TicketCreate.model_validate(ticket_values(w, ticket_for="graphics"))
    tickets.create_ticket(db, w.reporter, pending, Source.WEB, at(0))
    internal = TicketCreate.model_validate(ticket_values(w, approval_section_id=None))
    open_ticket = tickets.create_ticket(db, w.dev, internal, Source.INTERNAL, at(0))
    act(db, w.lead, open_ticket, Action.ASSIGN, 5, assignee_id=w.other_dev.id)

    result = dashboard(db)

    assert counts(result.by_status) == {
        "ticket_closed": 2,
        "pending_for_approval": 1,
        "waiting_in_queue": 1,
    }
    assert counts(result.by_ticket_for) == {"website": 3, "graphics": 1}
    assert counts(result.by_institute) == {w.institute.name: 3}
    assert counts(result.open_per_developer) == {w.other_dev.name: 1}
    assert result.avg_hours_queue_to_close == 2.0


def test_dashboard_with_no_tickets(db, world):
    result = dashboard(db)

    assert result.by_status == []
    assert result.avg_hours_queue_to_close is None


def test_dashboard_is_for_lead_and_admin(as_user, world):
    url = "/api/v1/dashboard"

    assert as_user(world.lead).get(url).status_code == 200
    assert as_user(world.admin).get(url).status_code == 200
    for user in (world.reporter, world.approver, world.dev):
        assert as_user(user).get(url).status_code == 403
