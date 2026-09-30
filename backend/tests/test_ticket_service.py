from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.enums import Action, EventType, Role, Source, Status
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.models import Ticket, TicketEvent
from app.schemas.tickets import ActionBody, TicketCreate, TicketFilters
from app.services import tickets, timer
from tests.factories import make_user, ticket_values

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def new_ticket(db, w, **overrides) -> Ticket:
    data = TicketCreate.model_validate(ticket_values(w, **overrides))
    return tickets.create_ticket(db, w.reporter, data, Source.WEB, at(0))


def act(db, actor, ticket, action, now=None, **body) -> Ticket:
    return tickets.apply_action(db, actor, ticket.id, action, ActionBody.model_validate(body), now)


def queued_ticket(db, w) -> Ticket:
    """Approved and assigned to w.dev, not started."""
    ticket = new_ticket(db, w)
    act(db, w.approver, ticket, Action.APPROVE, at(5), remark="Approved")
    act(db, w.lead, ticket, Action.ASSIGN, at(10), assignee_id=w.dev.id, estimate_minutes=120)
    return ticket


def event_types(db, ticket) -> list[EventType]:
    return list(
        db.scalars(
            select(TicketEvent.event_type)
            .where(TicketEvent.ticket_id == ticket.id)
            .order_by(TicketEvent.id)
        )
    )


def test_web_ticket_starts_pending_with_a_created_event(db, world):
    ticket = new_ticket(db, world)

    assert ticket.status is Status.PENDING_APPROVAL
    assert ticket.number.startswith("CS-")
    assert ticket.institute_id == world.institute.id
    assert ticket.approval_section_id == world.section.id
    event = db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)).one()
    assert event.event_type is EventType.CREATED
    assert event.to_value == "pending_for_approval"


def test_internal_ticket_skips_approval(db, world):
    data = TicketCreate.model_validate(ticket_values(world, approval_section_id=None))

    ticket = tickets.create_ticket(db, world.dev, data, Source.INTERNAL, at(0))

    assert ticket.status is Status.WAITING_IN_QUEUE
    assert ticket.approval_section_id is None
    assert ticket.source is Source.INTERNAL


def test_create_checks_role_and_section(db, world):
    data = TicketCreate.model_validate(ticket_values(world))
    no_section = TicketCreate.model_validate(ticket_values(world, approval_section_id=None))
    bad_section = TicketCreate.model_validate(ticket_values(world, approval_section_id=999999))

    with pytest.raises(Forbidden):
        tickets.create_ticket(db, world.reporter, data, Source.INTERNAL)
    with pytest.raises(Forbidden):
        tickets.create_ticket(db, world.approver, data, Source.WEB)
    with pytest.raises(Invalid):
        tickets.create_ticket(db, world.reporter, no_section, Source.WEB)
    with pytest.raises(Invalid):
        tickets.create_ticket(db, world.reporter, bad_section, Source.WEB)


def test_happy_path_records_events_and_time(db, world):
    w = world
    ticket = queued_ticket(db, w)
    assert ticket.status is Status.WAITING_IN_QUEUE
    assert ticket.assignee_id == w.dev.id
    assert ticket.estimate_minutes == 120

    act(db, w.dev, ticket, Action.START, at(20))
    assert ticket.status is Status.IN_PROCESS
    act(db, w.dev, ticket, Action.CLOSE, at(65), remark="Fixed the template")

    assert ticket.status is Status.CLOSED
    assert ticket.closed_at == at(65)
    assert timer.open_session(db, ticket.id) is None
    assert timer.seconds_spent(db, ticket.id, at(500)) == 45 * 60
    assert event_types(db, ticket) == [
        EventType.CREATED,
        EventType.STATUS_CHANGE,
        EventType.ASSIGN,
        EventType.ESTIMATE_CHANGE,
        EventType.STATUS_CHANGE,
        EventType.STATUS_CHANGE,
    ]
    assign = db.scalars(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id, TicketEvent.event_type == EventType.ASSIGN
        )
    ).one()
    assert assign.to_value == str(w.dev.id)
    assert assign.suggested_by == "lead"


@pytest.mark.parametrize("remark", [None, "", "   "])
def test_remark_is_required_where_the_spec_says_so(db, world, remark):
    ticket = new_ticket(db, world)

    with pytest.raises(Invalid):
        act(db, world.approver, ticket, Action.APPROVE, remark=remark)

    assert ticket.status is Status.PENDING_APPROVAL


def test_side_status_loop_from_in_process(db, world):
    w = world
    ticket = queued_ticket(db, w)
    act(db, w.dev, ticket, Action.START, at(20))

    act(
        db,
        w.dev,
        ticket,
        Action.REQUEST_INFO,
        at(30),
        side_status="clarification_required",
        remark="Which login?",
    )
    assert ticket.status is Status.CLARIFICATION_REQUIRED
    assert ticket.previous_status is Status.IN_PROCESS
    assert timer.open_session(db, ticket.id) is None

    act(db, w.reporter, ticket, Action.REPLY, at(90), remark="The student login.")
    assert ticket.status is Status.IN_PROCESS
    assert ticket.previous_status is None
    assert timer.open_session(db, ticket.id) is None  # does not restart by itself

    act(db, w.dev, ticket, Action.RESUME, at(100))
    act(db, w.dev, ticket, Action.CLOSE, at(115), remark="Done")
    assert timer.seconds_spent(db, ticket.id, at(500)) == (10 + 15) * 60


def test_side_status_from_pending_returns_to_pending(db, world):
    ticket = new_ticket(db, world)

    act(
        db,
        world.approver,
        ticket,
        Action.REQUEST_INFO,
        side_status="poor_quality_images",
        remark="Screenshot is unreadable",
    )
    act(db, world.reporter, ticket, Action.REPLY, remark="Attached a clearer one.")

    assert ticket.status is Status.PENDING_APPROVAL


def test_reassign_in_process_returns_to_queue_and_stops_timer(db, world):
    w = world
    ticket = queued_ticket(db, w)
    act(db, w.dev, ticket, Action.START, at(20))

    act(db, w.lead, ticket, Action.ASSIGN, at(50), assignee_id=w.other_dev.id)

    assert ticket.status is Status.WAITING_IN_QUEUE
    assert ticket.assignee_id == w.other_dev.id
    assert timer.open_session(db, ticket.id) is None
    assert timer.seconds_spent(db, ticket.id, at(500)) == 30 * 60
    reassign = db.scalars(
        select(TicketEvent).where(
            TicketEvent.ticket_id == ticket.id, TicketEvent.event_type == EventType.REASSIGN
        )
    ).one()
    assert (reassign.from_value, reassign.to_value) == (str(w.dev.id), str(w.other_dev.id))


def test_assign_validates_the_assignee(db, world):
    w = world
    ticket = queued_ticket(db, w)
    inactive = make_user(db, Role.DEVELOPER, is_active=False)

    for bad_id in (None, w.reporter.id, inactive.id, 999999):
        with pytest.raises(Invalid):
            act(db, w.lead, ticket, Action.ASSIGN, assignee_id=bad_id)
    with pytest.raises(Conflict):
        act(db, w.lead, ticket, Action.ASSIGN, assignee_id=w.dev.id)


def test_set_estimate_records_the_change(db, world):
    ticket = queued_ticket(db, world)

    act(db, world.lead, ticket, Action.SET_ESTIMATE, estimate_minutes=45)

    assert ticket.estimate_minutes == 45
    change = db.scalars(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket.id,
            TicketEvent.event_type == EventType.ESTIMATE_CHANGE,
        )
        .order_by(TicketEvent.id.desc())
    ).first()
    assert change is not None
    assert (change.from_value, change.to_value) == ("120", "45")
    with pytest.raises(Invalid):
        act(db, world.lead, ticket, Action.SET_ESTIMATE)


def test_timer_conflicts(db, world):
    w = world
    ticket = queued_ticket(db, w)
    act(db, w.dev, ticket, Action.START, at(20))

    with pytest.raises(Conflict):
        act(db, w.dev, ticket, Action.START, at(21))
    with pytest.raises(Conflict):
        act(db, w.dev, ticket, Action.RESUME, at(22))
    act(db, w.dev, ticket, Action.PAUSE, at(30))
    with pytest.raises(Conflict):
        act(db, w.dev, ticket, Action.PAUSE, at(31))

    assert ticket.status is Status.IN_PROCESS
    assert timer.seconds_spent(db, ticket.id, at(500)) == 10 * 60


def test_final_tickets_accept_no_actions(db, world):
    w = world
    rejected = new_ticket(db, w)
    act(db, w.approver, rejected, Action.REJECT, remark="Out of scope")

    with pytest.raises(Conflict):
        act(db, w.approver, rejected, Action.APPROVE, remark="Changed my mind")
    assert rejected.status is Status.REJECTED


def test_visibility(db, world):
    w = world
    ticket = new_ticket(db, w)

    for viewer in (w.reporter, w.approver, w.lead, w.dev, w.admin):
        assert tickets.get_visible_ticket(db, viewer, ticket.id).id == ticket.id
    for stranger in (w.other_reporter, w.other_approver):
        with pytest.raises(NotFound):
            tickets.get_visible_ticket(db, stranger, ticket.id)
    with pytest.raises(NotFound):
        tickets.get_visible_ticket(db, w.lead, 999999)
    with pytest.raises(NotFound):
        act(db, w.other_approver, ticket, Action.APPROVE, remark="Approved")


def test_approver_without_section_sees_nothing(db, world):
    w = world
    data = TicketCreate.model_validate(ticket_values(w, approval_section_id=None))
    internal = tickets.create_ticket(db, w.dev, data, Source.INTERNAL)
    new_ticket(db, w)
    unassigned_approver = make_user(db, Role.APPROVER)

    with pytest.raises(NotFound):
        tickets.get_visible_ticket(db, unassigned_approver, internal.id)
    with pytest.raises(NotFound):
        tickets.get_visible_ticket(db, w.approver, internal.id)
    items, total = tickets.list_tickets(db, unassigned_approver, TicketFilters())
    assert (items, total) == ([], 0)


def test_messages_are_events(db, world):
    ticket = new_ticket(db, world)

    event = tickets.add_message(db, world.lead, ticket.id, "Looking into it.", at(3))

    assert event.event_type is EventType.MESSAGE
    assert event.body == "Looking into it."
    assert event.actor_id == world.lead.id
    with pytest.raises(NotFound):
        tickets.add_message(db, world.other_reporter, ticket.id, "Hello")


def test_no_messages_on_final_ticket(db, world):
    ticket = new_ticket(db, world)
    act(db, world.approver, ticket, Action.REJECT, remark="Out of scope")

    with pytest.raises(Conflict):
        tickets.add_message(db, world.reporter, ticket.id, "Please reconsider")


def test_list_scopes_filters_and_pages(db, world):
    w = world
    mine = queued_ticket(db, w)
    pending = new_ticket(db, w, ticket_for="graphics")
    other = tickets.create_ticket(
        db,
        w.other_reporter,
        TicketCreate.model_validate(ticket_values(w, approval_section_id=w.other_section.id)),
        Source.WEB,
        at(1),
    )

    def ids(actor, **filters) -> set[int]:
        items, _ = tickets.list_tickets(db, actor, TicketFilters.model_validate(filters))
        return {t.id for t in items}

    assert ids(w.lead) == {mine.id, pending.id, other.id}
    assert ids(w.reporter) == {mine.id, pending.id}
    assert ids(w.approver) == {mine.id, pending.id}
    assert ids(w.other_approver) == {other.id}
    assert ids(w.lead, status="waiting_in_queue") == {mine.id}
    assert ids(w.lead, ticket_for="graphics") == {pending.id}
    assert ids(w.lead, assignee_id=w.dev.id) == {mine.id}
    assert ids(w.dev, mine=True) == {mine.id}
    assert ids(w.other_dev, mine=True) == set()
    page, total = tickets.list_tickets(db, w.lead, TicketFilters(limit=2, offset=0))
    assert (len(page), total) == (2, 3)


def test_bulk_assign_skips_tickets_already_with_that_developer(db, world):
    w = world
    first = new_ticket(db, w)
    second = queued_ticket(db, w)
    act(db, w.approver, first, Action.APPROVE, remark="Approved")

    result = tickets.bulk_assign(db, w.lead, [first.id, second.id, first.id], w.dev.id, 30)

    assert {t.id for t in result} == {first.id, second.id}
    assert first.assignee_id == w.dev.id and first.estimate_minutes == 30
    assert second.estimate_minutes == 120  # untouched: already assigned to w.dev
    with pytest.raises(Conflict):
        tickets.bulk_assign(db, w.lead, [new_ticket(db, w).id], w.dev.id)  # still pending


def test_detail_has_timeline_time_and_allowed_actions(db, world):
    w = world
    ticket = queued_ticket(db, w)
    act(db, w.dev, ticket, Action.START, at(20))

    detail = tickets.ticket_detail(db, w.dev, ticket, at(50))

    assert detail.status is Status.IN_PROCESS
    assert detail.seconds_spent == 30 * 60
    assert detail.timer_running is True
    assert detail.assignee is not None and detail.assignee.id == w.dev.id
    assert [e.event_type for e in detail.events][0] is EventType.CREATED
    assert set(detail.allowed_actions) == {
        Action.PAUSE,
        Action.RESUME,
        Action.REQUEST_INFO,
        Action.CLOSE,
    }
    assert tickets.ticket_detail(db, w.reporter, ticket, at(50)).allowed_actions == []


def test_bulk_assign_refuses_a_closed_ticket_already_with_that_developer(db, world):
    w = world
    ticket = queued_ticket(db, w)
    act(db, w.dev, ticket, Action.START, at(20))
    act(db, w.dev, ticket, Action.CLOSE, at(30), remark="Done")

    with pytest.raises(Conflict):
        tickets.bulk_assign(db, w.lead, [ticket.id], w.dev.id)
