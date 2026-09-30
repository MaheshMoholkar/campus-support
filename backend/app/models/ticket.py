from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Sequence, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EventType, Source, Status, TicketFor, TicketType
from app.models.base import Base, str_enum, utcnow
from app.models.org import User

ticket_number_seq = Sequence("ticket_number_seq")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(12), unique=True)
    source: Mapped[Source] = mapped_column(str_enum(Source))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    institute_id: Mapped[int | None] = mapped_column(ForeignKey("institutes.id"), index=True)
    approval_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("approval_sections.id"), index=True
    )
    ticket_for: Mapped[TicketFor] = mapped_column(str_enum(TicketFor))
    ticket_type: Mapped[TicketType] = mapped_column(str_enum(TicketType))
    erp_module_id: Mapped[int | None] = mapped_column(ForeignKey("erp_modules.id"))
    page_url: Mapped[str | None] = mapped_column(String(2000))
    description: Mapped[str] = mapped_column(Text)
    contact_number: Mapped[str | None] = mapped_column(String(20))
    extension: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[Status] = mapped_column(str_enum(Status), index=True)
    previous_status: Mapped[Status | None] = mapped_column(str_enum(Status))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    estimate_minutes: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    events: Mapped[list[TicketEvent]] = relationship(
        back_populates="ticket", order_by="TicketEvent.id"
    )
    attachments: Mapped[list[Attachment]] = relationship(order_by="Attachment.id")


class TicketEvent(Base):
    """Append-only history: never updated or deleted."""

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[EventType] = mapped_column(str_enum(EventType))
    from_value: Mapped[str | None] = mapped_column(String(100))
    to_value: Mapped[str | None] = mapped_column(String(100))
    body: Mapped[str | None] = mapped_column(Text)
    suggested_by: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship()


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("ticket_events.id"))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkSession(Base):
    """One timer segment. At most one open segment per ticket (partial unique index)."""

    __tablename__ = "work_sessions"
    __table_args__ = (
        Index(
            "uq_work_sessions_one_open",
            "ticket_id",
            unique=True,
            postgresql_where=text("stopped_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    developer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
