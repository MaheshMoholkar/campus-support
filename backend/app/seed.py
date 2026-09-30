"""Invented demo data for Tarangini University. Run: uv run python -m app.seed"""

import argparse
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.enums import Action, Role, Source, TicketFor, TicketType
from app.core.security import hash_password
from app.models import ApprovalSection, ErpModule, Institute, User
from app.schemas.tickets import ActionBody, TicketCreate
from app.services import tickets

DOMAIN = "tarangini.example"
ERP_BASE = f"https://erp.{DOMAIN}"
SITE_BASE = f"https://www.{DOMAIN}"
TICKET_COUNT = 120

INSTITUTES = [
    ("Tarangini Institute of Engineering", "TIE"),
    ("Tarangini College of Architecture", "TCA"),
    ("Tarangini School of Management", "TSM"),
    ("Tarangini College of Pharmacy", "TCP"),
    ("Tarangini Law College", "TLC"),
    ("Tarangini College of Nursing", "TCN"),
    ("Tarangini Institute of Design", "TID"),
    ("Tarangini College of Education", "TCE"),
    ("Tarangini School of Computer Applications", "TSCA"),
    ("Tarangini College of Arts", "TCAR"),
    ("Tarangini College of Commerce", "TCC"),
    ("Tarangini College of Science", "TCS"),
    ("Tarangini Institute of Hotel Management", "TIHM"),
    ("Tarangini School of Journalism", "TSJ"),
    ("Tarangini College of Physiotherapy", "TCPT"),
    ("Tarangini Institute of Biotechnology", "TIB"),
    ("Tarangini College of Agriculture", "TCAG"),
    ("Tarangini School of Music", "TSMU"),
    ("Tarangini Polytechnic", "TPOLY"),
    ("Tarangini Junior College", "TJC"),
    ("Tarangini School of Distance Learning", "TSDL"),
    ("Tarangini Research Centre", "TRC"),
]
SECTIONS = [
    "Registrar Office",
    "Examination Section",
    "Accounts Section",
    "Admissions Office",
    "Central Library",
    "Principal Office",
]
MODULES = [
    ("Admissions", "/admissions"),
    ("Examination", "/exam"),
    ("Fees", "/fees"),
    ("Library", "/library"),
    ("HR and Payroll", "/hr"),
    ("Hostel", "/hostel"),
    ("Timetable", "/timetable"),
    ("Student Portal", "/student"),
]
FIRST_NAMES = [
    "Asha",
    "Rohan",
    "Meera",
    "Kiran",
    "Sanjay",
    "Pooja",
    "Nikhil",
    "Farah",
    "Imran",
    "Lata",
    "Deepak",
    "Sneha",
    "Arjun",
    "Tanvi",
    "Vivek",
    "Rekha",
    "Omkar",
    "Nisha",
    "Harish",
    "Gauri",
]
LAST_NAMES = [
    "Kale",
    "Shinde",
    "Pawar",
    "Joshi",
    "Naik",
    "Desai",
    "More",
    "Sawant",
    "Bhosale",
    "Gokhale",
    "Thakur",
    "Rane",
    "Salvi",
    "Kadam",
    "Mane",
    "Dalvi",
    "Shaikh",
    "Fernandes",
    "Iyer",
    "Verma",
]
# (ticket for, type, ERP module name or None, page path, description)
REQUESTS: list[tuple[TicketFor, TicketType, str | None, str, str]] = [
    (
        TicketFor.CAMPUS_ERP,
        TicketType.BUG_REPORT,
        "Fees",
        "/fees/receipt",
        "Fee receipt PDF shows the wrong academic year for second-year students.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.NEW_REQUIREMENT,
        "Examination",
        "/exam/seating",
        "Need a seating arrangement report grouped by hall and roll number for the term exam.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.MODIFICATION,
        "Admissions",
        "/admissions/form",
        "Add a field for the entrance test score on the admission form, after the category field.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.DATABASE_UPDATION,
        "HR and Payroll",
        "/hr/staff",
        "Update the designation of twelve staff members as per the attached promotion order.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.API_CREATION,
        "Library",
        "/library/issue",
        "Need an API that returns books currently issued to a student, for the mobile app.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.API_UPDATION,
        "Student Portal",
        "/student/profile",
        "The profile API should also return the mentor name and the division.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.BUG_REPORT,
        "Timetable",
        "/timetable/week",
        "Weekly timetable shows Saturday lectures under Friday after the last update.",
    ),
    (
        TicketFor.CAMPUS_ERP,
        TicketType.MODIFICATION,
        "Hostel",
        "/hostel/allotment",
        "Room allotment list should be sortable by floor and show the warden's extension.",
    ),
    (
        TicketFor.WEBSITE,
        TicketType.UPLOADING,
        None,
        "/notices",
        "Please upload the attached notice about the revised holiday list to the notices page.",
    ),
    (
        TicketFor.WEBSITE,
        TicketType.BUG_REPORT,
        None,
        "/contact",
        "The contact form shows an error after submit and the message is not delivered.",
    ),
    (
        TicketFor.WEBSITE,
        TicketType.MODIFICATION,
        None,
        "/faculty",
        "Update the faculty page with the new head of department and remove two retired members.",
    ),
    (
        TicketFor.BLOGS,
        TicketType.UPLOADING,
        None,
        "/blog",
        "Publish the attached article about the annual science exhibition with its photographs.",
    ),
    (
        TicketFor.EMAILS,
        TicketType.NEW_REQUIREMENT,
        None,
        "/mail",
        "Create official email accounts for five newly joined faculty members of the department.",
    ),
    (
        TicketFor.GRAPHICS,
        TicketType.NEW_REQUIREMENT,
        None,
        "/events",
        "Need a banner and a poster for the inter-college sports meet to be held next month.",
    ),
    (
        TicketFor.SEO,
        TicketType.MODIFICATION,
        None,
        "/admissions",
        "Improve the page title and description of the admissions page for the new intake.",
    ),
    (
        TicketFor.WEBSITE,
        TicketType.OTHER,
        None,
        "/gallery",
        "Gallery images load very slowly on mobile; please check what can be improved.",
    ),
]
# Weighted towards closed tickets, which later milestones use as history.
SCENARIO_ORDER = [
    "closed",
    "closed",
    "pending",
    "closed",
    "approved",
    "closed",
    "assigned",
    "paused",
    "closed",
    "rejected",
    "clarify",
    "insufficient",
]


def _person(i: int) -> str:
    return f"{FIRST_NAMES[i % 20]} {LAST_NAMES[(i * 7 + i // 20) % 20]}"


def reset(db: Session) -> None:
    db.execute(
        text(
            "TRUNCATE attachments, work_sessions, ticket_events, tickets, users, "
            "erp_modules, approval_sections, institutes RESTART IDENTITY CASCADE"
        )
    )
    db.execute(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1"))


def seed(db: Session, password: str, now: datetime) -> dict[str, int]:
    if db.execute(select(func.count()).select_from(User)).scalar_one() > 0:
        raise SystemExit("Database already has users. Use --reset to wipe and reseed.")

    institutes = [Institute(name=name, code=code) for name, code in INSTITUTES]
    sections = [ApprovalSection(name=name) for name in SECTIONS]
    modules = [ErpModule(name=name, url_prefix=ERP_BASE + path) for name, path in MODULES]
    db.add_all([*institutes, *sections, *modules])
    db.flush()
    module_ids = {module.name: module.id for module in modules}

    password_hash = hash_password(password)

    def user(i: int, login: str, role: Role, **fields) -> User:
        return User(
            name=_person(i),
            email=f"{login}@{DOMAIN}",
            password_hash=password_hash,
            role=role,
            **fields,
        )

    admin = user(0, "admin", Role.ADMIN)
    lead = user(1, "lead", Role.LEAD)
    developers = [user(2 + i, f"dev{i + 1}", Role.DEVELOPER) for i in range(4)]
    approvers = [
        user(6 + i, f"approver{i + 1}", Role.APPROVER, approval_section_id=section.id)
        for i, section in enumerate(sections)
    ]
    reporters = [
        user(
            12 + i,
            f"reporter{i + 1}",
            Role.REPORTER,
            institute_id=institute.id,
            extension=str(200 + i),
            contact_number=f"00000{10000 + i}",
        )
        for i, institute in enumerate(institutes)
    ]
    people = [admin, lead, *developers, *approvers, *reporters]
    db.add_all(people)
    db.flush()

    for i in range(TICKET_COUNT):
        created = now - timedelta(days=TICKET_COUNT - i, hours=i % 7)
        ticket_for, ticket_type, module_name, path, description = REQUESTS[i % len(REQUESTS)]
        developer = developers[i % len(developers)]
        base = ERP_BASE if ticket_for is TicketFor.CAMPUS_ERP else SITE_BASE
        values = {
            "ticket_for": ticket_for,
            "ticket_type": ticket_type,
            "erp_module_id": module_ids.get(module_name) if module_name else None,
            "page_url": base + path,
            "description": description,
        }
        if i % 10 == 9:
            tickets.create_ticket(
                db, developer, TicketCreate.model_validate(values), Source.INTERNAL, created
            )
            continue

        section_index = i % len(sections)
        reporter = reporters[i % len(reporters)]
        approver = approvers[section_index]
        values.update(
            approval_section_id=sections[section_index].id,
            contact_number=reporter.contact_number,
            extension=reporter.extension,
        )
        ticket = tickets.create_ticket(
            db, reporter, TicketCreate.model_validate(values), Source.WEB, created
        )

        approve = (30, approver, Action.APPROVE, {"remark": "Approved. Please take this up."})
        assign = (
            90,
            lead,
            Action.ASSIGN,
            {"assignee_id": developer.id, "estimate_minutes": 60 + 30 * (i % 5)},
        )
        start = (240, developer, Action.START, {})
        steps = {
            "pending": [],
            "approved": [approve],
            "assigned": [approve, assign],
            "paused": [approve, assign, start, (300, developer, Action.PAUSE, {})],
            "closed": [
                approve,
                assign,
                start,
                (
                    300 + 20 * (i % 6),
                    developer,
                    Action.CLOSE,
                    {"remark": "Done and verified on the live page."},
                ),
            ],
            "rejected": [(45, approver, Action.REJECT, {"remark": "Not in scope for this term."})],
            "clarify": [
                (
                    40,
                    approver,
                    Action.REQUEST_INFO,
                    {
                        "side_status": "clarification_required",
                        "remark": "Which page or report is this about?",
                    },
                )
            ],
            "insufficient": [
                approve,
                assign,
                start,
                (
                    270,
                    developer,
                    Action.REQUEST_INFO,
                    {
                        "side_status": "insufficient_data",
                        "remark": "Please share the list this should apply to.",
                    },
                ),
            ],
        }[SCENARIO_ORDER[i % len(SCENARIO_ORDER)]]
        for minutes, actor, action, body in steps:
            tickets.apply_action(
                db,
                actor,
                ticket.id,
                action,
                ActionBody.model_validate(body),
                created + timedelta(minutes=minutes),
            )

    db.flush()
    return {
        "institutes": len(institutes),
        "sections": len(sections),
        "modules": len(modules),
        "users": len(people),
        "tickets": TICKET_COUNT,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed invented demo data.")
    parser.add_argument("--reset", action="store_true", help="delete ALL existing data first")
    parser.add_argument("--password", default=os.environ.get("SEED_PASSWORD", "campus-demo"))
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            reset(db)
        summary = seed(db, args.password, datetime.now(UTC))
        db.commit()
    print("Seeded:", summary)
    print(f"Logins: admin@, lead@, dev1@, approver1@, reporter1@ ... (domain {DOMAIN})")


if __name__ == "__main__":
    main()
