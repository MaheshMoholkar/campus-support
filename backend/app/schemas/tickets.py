from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Action, EventType, Source, Status, TicketFor, TicketType


class Stripped(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TicketCreate(Stripped):
    approval_section_id: int | None = None
    ticket_for: TicketFor
    ticket_type: TicketType
    erp_module_id: int | None = None
    page_url: str | None = Field(default=None, max_length=2000)
    description: str = Field(min_length=10, max_length=10000)
    contact_number: str | None = Field(default=None, max_length=20)
    extension: str | None = Field(default=None, max_length=10)
    attachment_keys: list[str] = Field(default_factory=list, max_length=5)


class ActionBody(Stripped):
    remark: str | None = Field(default=None, max_length=5000)
    side_status: Status | None = None
    assignee_id: int | None = None
    estimate_minutes: int | None = Field(default=None, ge=1, le=43200)
    attachment_keys: list[str] = Field(default_factory=list, max_length=5)


class MessageCreate(Stripped):
    body: str = Field(min_length=1, max_length=10000)
    attachment_keys: list[str] = Field(default_factory=list, max_length=5)


class BulkAssign(BaseModel):
    ticket_ids: list[int] = Field(min_length=1, max_length=200)
    assignee_id: int
    estimate_minutes: int | None = Field(default=None, ge=1, le=43200)


class TicketFilters(BaseModel):
    institute_id: int | None = None
    ticket_for: TicketFor | None = None
    ticket_type: TicketType | None = None
    status: Status | None = None
    assignee_id: int | None = None
    mine: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class FromOrm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserBrief(FromOrm):
    id: int
    name: str


class TicketOut(FromOrm):
    id: int
    number: str
    source: Source
    status: Status
    previous_status: Status | None
    ticket_for: TicketFor
    ticket_type: TicketType
    description: str
    page_url: str | None
    institute_id: int | None
    approval_section_id: int | None
    erp_module_id: int | None
    reporter: UserBrief
    assignee: UserBrief | None
    estimate_minutes: int | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class EventOut(FromOrm):
    id: int
    event_type: EventType
    actor: UserBrief | None
    from_value: str | None
    to_value: str | None
    body: str | None
    suggested_by: str | None
    created_at: datetime


class AttachmentOut(FromOrm):
    id: int
    event_id: int | None
    file_name: str
    mime_type: str
    size_bytes: int


class TicketDetail(TicketOut):
    contact_number: str | None
    extension: str | None
    events: list[EventOut]
    attachments: list[AttachmentOut]
    seconds_spent: int
    timer_running: bool
    allowed_actions: list[Action]


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int
