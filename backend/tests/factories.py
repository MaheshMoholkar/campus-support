from dataclasses import dataclass
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


def build_user(role: Role, **fields) -> User:
    i = next(_n)
    values = {
        "name": f"User {i}",
        "email": f"user{i}@tarangini.example",
        "password_hash": "unusable",
        "role": role,
    }
    values.update(fields)
    return User(**values)


def make_user(db: Session, role: Role, **fields) -> User:
    return _save(db, build_user(role, **fields))


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


@dataclass
class World:
    institute: Institute
    section: ApprovalSection
    other_section: ApprovalSection
    reporter: User
    other_reporter: User
    approver: User
    other_approver: User
    lead: User
    dev: User
    other_dev: User
    admin: User


def make_world(db: Session) -> World:
    # One flush and one commit for the whole world: each database round trip is slow
    # when Postgres is on another machine.
    i = next(_n)
    institute = Institute(name=f"Institute {i}", code=f"I{i}")
    section = ApprovalSection(name=f"Section {i}a")
    other_section = ApprovalSection(name=f"Section {i}b")
    db.add_all([institute, section, other_section])
    db.flush()
    world = World(
        institute=institute,
        section=section,
        other_section=other_section,
        reporter=build_user(Role.REPORTER, institute_id=institute.id),
        other_reporter=build_user(Role.REPORTER, institute_id=institute.id),
        approver=build_user(Role.APPROVER, approval_section_id=section.id),
        other_approver=build_user(Role.APPROVER, approval_section_id=other_section.id),
        lead=build_user(Role.LEAD),
        dev=build_user(Role.DEVELOPER),
        other_dev=build_user(Role.DEVELOPER),
        admin=build_user(Role.ADMIN),
    )
    db.add_all(
        [
            world.reporter,
            world.other_reporter,
            world.approver,
            world.other_approver,
            world.lead,
            world.dev,
            world.other_dev,
            world.admin,
        ]
    )
    db.commit()
    return world


def ticket_values(world: World, **overrides) -> dict:
    values = {
        "approval_section_id": world.section.id,
        "ticket_for": "website",
        "ticket_type": "bug_report",
        "description": "The admissions page shows a blank screen after login.",
        "page_url": "https://www.tarangini.example/admissions",
    }
    values.update(overrides)
    return values
