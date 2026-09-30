from itertools import count

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Role, Source, Status, TicketFor, TicketType
from app.models import (
    ApprovalSection,
    ErpModule,
    Institute,
    Ticket,
    User,
    ticket_number_seq,
)

_n = count(1)


def _save[T](db: Session, obj: T) -> T:
    db.add(obj)
    db.commit()
    return obj


def make_institute(db: Session) -> Institute:
    i = next(_n)
    return _save(db, Institute(name=f"Institute {i}", code=f"I{i}"))


def make_section(db: Session) -> ApprovalSection:
    return _save(db, ApprovalSection(name=f"Section {next(_n)}"))


def make_module(db: Session) -> ErpModule:
    i = next(_n)
    return _save(
        db, ErpModule(name=f"Module {i}", url_prefix=f"https://erp.tarangini.example/m{i}")
    )


def make_user(db: Session, role: Role, **fields) -> User:
    i = next(_n)
    values = {
        "name": f"User {i}",
        "email": f"user{i}@tarangini.example",
        "password_hash": "unusable",
        "role": role,
    }
    values.update(fields)
    return _save(db, User(**values))


def make_ticket_row(db: Session, reporter: User, **fields) -> Ticket:
    seq = db.execute(select(ticket_number_seq.next_value())).scalar_one()
    values = {
        "number": f"CS-{seq:06d}",
        "source": Source.WEB,
        "reporter_id": reporter.id,
        "ticket_for": TicketFor.WEBSITE,
        "ticket_type": TicketType.BUG_REPORT,
        "description": "The contact page shows an error after submit.",
        "status": Status.PENDING_APPROVAL,
    }
    values.update(fields)
    return _save(db, Ticket(**values))
