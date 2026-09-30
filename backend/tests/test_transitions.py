import pytest

from app.core.enums import FINAL_STATUSES, Action, Role, Status
from app.core.errors import Conflict, Forbidden, Invalid
from app.services.transitions import TRANSITIONS, Actor, TicketState, allowed_actions, resolve

PENDING = Status.PENDING_APPROVAL
QUEUE = Status.WAITING_IN_QUEUE
IN_PROCESS = Status.IN_PROCESS
CLOSED = Status.CLOSED
REJECTED = Status.REJECTED
CLARIFY = Status.CLARIFICATION_REQUIRED
INSUFFICIENT = Status.INSUFFICIENT_DATA
POOR = Status.POOR_QUALITY_IMAGES

REPORTER = Actor(1, Role.REPORTER, None)
APPROVER = Actor(2, Role.APPROVER, 10)
OTHER_APPROVER = Actor(3, Role.APPROVER, 11)
NO_SECTION_APPROVER = Actor(8, Role.APPROVER, None)
LEAD = Actor(4, Role.LEAD, None)
DEV = Actor(5, Role.DEVELOPER, None)
OTHER_DEV = Actor(6, Role.DEVELOPER, None)
ADMIN = Actor(7, Role.ADMIN, None)


def state(status, previous=None, assignee: int | None = DEV.id, section: int | None = 10):
    return TicketState(status, previous, REPORTER.id, assignee, section)


# (actor, ticket, action, side status, expected new status)
ALLOWED = [
    (APPROVER, state(PENDING), Action.APPROVE, None, QUEUE),
    (APPROVER, state(PENDING), Action.REJECT, None, REJECTED),
    (APPROVER, state(PENDING), Action.REQUEST_INFO, CLARIFY, CLARIFY),
    (LEAD, state(QUEUE), Action.ASSIGN, None, QUEUE),
    (LEAD, state(QUEUE), Action.SET_ESTIMATE, None, QUEUE),
    (LEAD, state(QUEUE), Action.REQUEST_INFO, INSUFFICIENT, INSUFFICIENT),
    (DEV, state(QUEUE), Action.REQUEST_INFO, POOR, POOR),
    (DEV, state(QUEUE), Action.START, None, IN_PROCESS),
    (DEV, state(IN_PROCESS), Action.PAUSE, None, IN_PROCESS),
    (DEV, state(IN_PROCESS), Action.RESUME, None, IN_PROCESS),
    (DEV, state(IN_PROCESS), Action.REQUEST_INFO, CLARIFY, CLARIFY),
    (LEAD, state(IN_PROCESS), Action.ASSIGN, None, QUEUE),
    (LEAD, state(IN_PROCESS), Action.SET_ESTIMATE, None, IN_PROCESS),
    (DEV, state(IN_PROCESS), Action.CLOSE, None, CLOSED),
    (REPORTER, state(CLARIFY, previous=PENDING), Action.REPLY, None, PENDING),
    (REPORTER, state(INSUFFICIENT, previous=QUEUE), Action.REPLY, None, QUEUE),
    (REPORTER, state(POOR, previous=IN_PROCESS), Action.REPLY, None, IN_PROCESS),
]

# Guard fails: 403
FORBIDDEN = [
    (OTHER_APPROVER, state(PENDING), Action.APPROVE),  # right role, wrong section
    (APPROVER, state(PENDING, section=None), Action.APPROVE),  # ticket has no section
    (NO_SECTION_APPROVER, state(PENDING, section=None), Action.APPROVE),  # None never matches
    (LEAD, state(PENDING), Action.APPROVE),
    (ADMIN, state(PENDING), Action.REJECT),
    (OTHER_DEV, state(QUEUE), Action.START),  # right role, not the assignee
    (DEV, state(QUEUE, assignee=None), Action.START),
    (DEV, state(QUEUE), Action.ASSIGN),
    (APPROVER, state(QUEUE), Action.REQUEST_INFO),  # approver acts only while pending
    (OTHER_DEV, state(IN_PROCESS), Action.CLOSE),
    (LEAD, state(IN_PROCESS), Action.CLOSE),
    (LEAD, state(IN_PROCESS), Action.REQUEST_INFO),
    (DEV, state(CLARIFY, previous=QUEUE), Action.REPLY),  # not the reporter
]

# No such transition: 409
NOT_ALLOWED = [
    (DEV, state(CLOSED), Action.CLOSE),
    (LEAD, state(CLOSED), Action.ASSIGN),
    (APPROVER, state(REJECTED), Action.APPROVE),
    (REPORTER, state(PENDING), Action.REPLY),
    (DEV, state(PENDING), Action.START),
    (DEV, state(IN_PROCESS), Action.START),
    (APPROVER, state(QUEUE), Action.APPROVE),
]


@pytest.mark.parametrize("actor,ticket,action,side,expected", ALLOWED)
def test_allowed_transitions(actor, ticket, action, side, expected):
    assert resolve(actor, ticket, action, side) == expected


def test_every_table_entry_is_covered_by_the_allowed_cases():
    assert {(ticket.status, action) for _, ticket, action, _, _ in ALLOWED} == set(TRANSITIONS)


@pytest.mark.parametrize("actor,ticket,action", FORBIDDEN)
def test_guard_failures_are_forbidden(actor, ticket, action):
    with pytest.raises(Forbidden):
        resolve(actor, ticket, action, CLARIFY)


@pytest.mark.parametrize("actor,ticket,action", NOT_ALLOWED)
def test_missing_transitions_are_conflicts(actor, ticket, action):
    with pytest.raises(Conflict):
        resolve(actor, ticket, action, CLARIFY)


@pytest.mark.parametrize("side", [None, Status.CLOSED, Status.WAITING_IN_QUEUE])
def test_request_info_needs_a_side_status(side):
    with pytest.raises(Invalid):
        resolve(APPROVER, state(PENDING), Action.REQUEST_INFO, side)


def test_reply_without_a_previous_status_is_a_conflict():
    with pytest.raises(Conflict):
        resolve(REPORTER, state(CLARIFY, previous=None), Action.REPLY)


def test_final_statuses_have_no_transitions():
    assert not [key for key in TRANSITIONS if key[0] in FINAL_STATUSES]


def test_allowed_actions_lists_what_the_viewer_can_do():
    assert set(allowed_actions(DEV, state(QUEUE))) == {Action.REQUEST_INFO, Action.START}
    assert set(allowed_actions(LEAD, state(QUEUE))) == {
        Action.ASSIGN,
        Action.SET_ESTIMATE,
        Action.REQUEST_INFO,
    }
    assert allowed_actions(REPORTER, state(QUEUE)) == []
    assert allowed_actions(DEV, state(CLOSED)) == []
