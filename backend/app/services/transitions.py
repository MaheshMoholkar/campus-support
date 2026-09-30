"""The only place that decides which status changes are allowed, and for whom."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.core.enums import SIDE_STATUSES, Action, Role, Status
from app.core.errors import Conflict, Forbidden, Invalid


@dataclass(frozen=True)
class Actor:
    id: int
    role: Role
    approval_section_id: int | None


@dataclass(frozen=True)
class TicketState:
    status: Status
    previous_status: Status | None
    reporter_id: int
    assignee_id: int | None
    approval_section_id: int | None


Guard = Callable[[Actor, TicketState], bool]


def is_section_approver(actor: Actor, ticket: TicketState) -> bool:
    return (
        actor.role is Role.APPROVER
        and ticket.approval_section_id is not None
        and actor.approval_section_id == ticket.approval_section_id
    )


def is_lead(actor: Actor, ticket: TicketState) -> bool:
    return actor.role is Role.LEAD


def is_assignee(actor: Actor, ticket: TicketState) -> bool:
    return ticket.assignee_id is not None and actor.id == ticket.assignee_id


def is_reporter(actor: Actor, ticket: TicketState) -> bool:
    return actor.id == ticket.reporter_id


def any_of(*guards: Guard) -> Guard:
    return lambda actor, ticket: any(guard(actor, ticket) for guard in guards)


class Target(Enum):
    SAME = "same"  # status does not change
    SIDE = "side"  # one of the three side statuses, chosen by the caller
    PREVIOUS = "previous"  # the status the ticket came from


@dataclass(frozen=True)
class Rule:
    guard: Guard
    target: Status | Target


_PENDING = Status.PENDING_APPROVAL
_QUEUE = Status.WAITING_IN_QUEUE
_IN_PROCESS = Status.IN_PROCESS

TRANSITIONS: dict[tuple[Status, Action], Rule] = {
    (_PENDING, Action.APPROVE): Rule(is_section_approver, _QUEUE),
    (_PENDING, Action.REJECT): Rule(is_section_approver, Status.REJECTED),
    (_PENDING, Action.REQUEST_INFO): Rule(is_section_approver, Target.SIDE),
    (_QUEUE, Action.ASSIGN): Rule(is_lead, Target.SAME),
    (_QUEUE, Action.SET_ESTIMATE): Rule(is_lead, Target.SAME),
    (_QUEUE, Action.REQUEST_INFO): Rule(any_of(is_lead, is_assignee), Target.SIDE),
    (_QUEUE, Action.START): Rule(is_assignee, _IN_PROCESS),
    (_IN_PROCESS, Action.PAUSE): Rule(is_assignee, Target.SAME),
    (_IN_PROCESS, Action.RESUME): Rule(is_assignee, Target.SAME),
    (_IN_PROCESS, Action.SET_ESTIMATE): Rule(is_lead, Target.SAME),
    (_IN_PROCESS, Action.REQUEST_INFO): Rule(is_assignee, Target.SIDE),
    (_IN_PROCESS, Action.ASSIGN): Rule(is_lead, _QUEUE),
    (_IN_PROCESS, Action.CLOSE): Rule(is_assignee, Status.CLOSED),
    **{(side, Action.REPLY): Rule(is_reporter, Target.PREVIOUS) for side in SIDE_STATUSES},
}


def resolve(
    actor: Actor, ticket: TicketState, action: Action, side_status: Status | None = None
) -> Status:
    """Return the status the ticket moves to, or raise if the action is not allowed."""
    rule = TRANSITIONS.get((ticket.status, action))
    if rule is None:
        raise Conflict(f"Cannot {action.value} a ticket that is {ticket.status.value}")
    if not rule.guard(actor, ticket):
        raise Forbidden("You are not allowed to do this on this ticket")
    if rule.target is Target.SAME:
        return ticket.status
    if rule.target is Target.SIDE:
        if side_status is None or side_status not in SIDE_STATUSES:
            raise Invalid(
                "side_status must be clarification_required, insufficient_data "
                "or poor_quality_images"
            )
        return side_status
    if rule.target is Target.PREVIOUS:
        if ticket.previous_status is None:
            raise Conflict("Ticket has no status to return to")
        return ticket.previous_status
    assert isinstance(rule.target, Status)
    return rule.target


def allowed_actions(actor: Actor, ticket: TicketState) -> list[Action]:
    return [
        action
        for (status, action), rule in TRANSITIONS.items()
        if status is ticket.status and rule.guard(actor, ticket)
    ]
