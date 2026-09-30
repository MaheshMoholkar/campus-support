import re
from pathlib import PurePath
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Invalid, NotFound
from app.models import Attachment, Ticket, TicketEvent, User
from app.services import tickets
from app.services.storage import Storage

MAX_BYTES = 10 * 1024 * 1024
MAX_FILES = 5
ALLOWED_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
    }
)


def _check(content_type: str, size_bytes: int) -> None:
    if content_type not in ALLOWED_TYPES:
        raise Invalid("This file type is not allowed")
    if size_bytes <= 0 or size_bytes > MAX_BYTES:
        raise Invalid("Files must be between 1 byte and 10 MB")


def new_upload(
    storage: Storage, actor: User, file_name: str, content_type: str, size_bytes: int
) -> tuple[str, str]:
    """Return (key, presigned PUT URL) for one file the caller is about to upload."""
    _check(content_type, size_bytes)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", PurePath(file_name).name)[:100]
    if not safe_name.strip("._"):
        raise Invalid("File name is not usable")
    key = f"uploads/{actor.id}/{uuid4().hex}/{safe_name}"
    return key, storage.presign_put(key, content_type)


def attach(
    db: Session,
    storage: Storage,
    actor: User,
    ticket: Ticket,
    keys: list[str],
    event: TicketEvent | None = None,
) -> list[Attachment]:
    if len(keys) > MAX_FILES:
        raise Invalid(f"At most {MAX_FILES} files per ticket or message")
    if len(set(keys)) != len(keys):
        raise Invalid("The same file is listed twice")
    created: list[Attachment] = []
    for key in keys:
        if not key.startswith(f"uploads/{actor.id}/"):
            raise Invalid("Unknown attachment")
        stored = storage.head(key)
        if stored is None:
            raise Invalid("Attachment was not uploaded")
        _check(stored.content_type, stored.size_bytes)
        already = db.execute(
            select(Attachment.id).where(Attachment.storage_key == key)
        ).scalar_one_or_none()
        if already is not None:
            raise Invalid("Attachment is already in use")
        attachment = Attachment(
            ticket_id=ticket.id,
            event_id=None if event is None else event.id,
            storage_key=key,
            file_name=key.rsplit("/", 1)[-1],
            mime_type=stored.content_type,
            size_bytes=stored.size_bytes,
            uploaded_by_id=actor.id,
        )
        db.add(attachment)
        created.append(attachment)
    db.flush()
    return created


def download_url(db: Session, storage: Storage, actor: User, attachment_id: int) -> str:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise NotFound("Attachment not found")
    tickets.get_visible_ticket(db, actor, attachment.ticket_id)  # raises NotFound if hidden
    return storage.presign_get(attachment.storage_key)
