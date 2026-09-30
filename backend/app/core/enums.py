from enum import StrEnum


class Role(StrEnum):
    REPORTER = "reporter"
    APPROVER = "approver"
    LEAD = "lead"
    DEVELOPER = "developer"
    ADMIN = "admin"


class Source(StrEnum):
    WEB = "web"
    INTERNAL = "internal"
    API = "api"


class Status(StrEnum):
    PENDING_APPROVAL = "pending_for_approval"
    WAITING_IN_QUEUE = "waiting_in_queue"
    IN_PROCESS = "in_process"
    CLOSED = "ticket_closed"
    REJECTED = "rejected_by_authority"
    CLARIFICATION_REQUIRED = "clarification_required"
    INSUFFICIENT_DATA = "insufficient_data"
    POOR_QUALITY_IMAGES = "poor_quality_images"


SIDE_STATUSES = frozenset(
    {Status.CLARIFICATION_REQUIRED, Status.INSUFFICIENT_DATA, Status.POOR_QUALITY_IMAGES}
)
FINAL_STATUSES = frozenset({Status.CLOSED, Status.REJECTED})


class TicketFor(StrEnum):
    CAMPUS_ERP = "campus_erp"
    WEBSITE = "website"
    BLOGS = "blogs"
    EMAILS = "emails"
    GRAPHICS = "graphics"
    SEO = "seo"


class TicketType(StrEnum):
    NEW_REQUIREMENT = "new_requirement"
    MODIFICATION = "modification"
    BUG_REPORT = "bug_report"
    API_CREATION = "api_creation"
    API_UPDATION = "api_updation"
    DATABASE_UPDATION = "database_updation"
    UPLOADING = "uploading"
    OTHER = "other"


class Action(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFO = "request_info"
    REPLY = "reply"
    ASSIGN = "assign"
    SET_ESTIMATE = "set_estimate"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    CLOSE = "close"


class EventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGE = "status_change"
    MESSAGE = "message"
    ASSIGN = "assign"
    REASSIGN = "reassign"
    ESTIMATE_CHANGE = "estimate_change"
