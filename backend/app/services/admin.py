from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import Conflict, Invalid, NotFound
from app.core.security import hash_password
from app.models import ApprovalSection, ErpModule, Institute, User
from app.schemas.admin import UserCreate, UserUpdate
from app.services.users import normalise_email

Master = Institute | ApprovalSection | ErpModule
MasterModel = type[Institute] | type[ApprovalSection] | type[ErpModule]


def _flush(db: Session, message: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflict(message) from exc


def list_rows(db: Session, model: MasterModel) -> list[Master]:
    return list(db.scalars(select(model).order_by(model.name)))


def create_row(db: Session, model: MasterModel, values: dict) -> Master:
    row = model(**values)
    db.add(row)
    _flush(db, "That name or code is already in use")
    return row


def update_row(db: Session, model: MasterModel, row_id: int, values: dict) -> Master:
    row = db.get(model, row_id)
    if row is None:
        raise NotFound("Not found")
    for field, value in values.items():
        setattr(row, field, value)
    _flush(db, "That name or code is already in use")
    return row


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name, User.id)))


def _check_refs(db: Session, role: Role, institute_id: int | None, section_id: int | None) -> None:
    if institute_id is not None and db.get(Institute, institute_id) is None:
        raise Invalid("Unknown institute")
    if section_id is not None and db.get(ApprovalSection, section_id) is None:
        raise Invalid("Unknown approval section")
    if role is Role.APPROVER and section_id is None:
        raise Invalid("An approver needs an approval section")


def create_user(db: Session, data: UserCreate) -> User:
    _check_refs(db, data.role, data.institute_id, data.approval_section_id)
    user = User(
        name=data.name,
        email=normalise_email(data.email),
        password_hash=hash_password(data.password),
        role=data.role,
        institute_id=data.institute_id,
        approval_section_id=data.approval_section_id,
        extension=data.extension,
        contact_number=data.contact_number,
    )
    db.add(user)
    _flush(db, "That email is already in use")
    return user


def update_user(db: Session, actor: User, user_id: int, data: UserUpdate) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    changes = data.model_dump(exclude_unset=True)
    if user.id == actor.id and (
        changes.get("is_active") is False or changes.get("role", Role.ADMIN) is not Role.ADMIN
    ):
        raise Conflict("You cannot deactivate or demote your own account")
    password = changes.pop("password", None)
    for field, value in changes.items():
        setattr(user, field, value)
    if password:
        user.password_hash = hash_password(password)
    _check_refs(db, user.role, user.institute_id, user.approval_section_id)
    db.flush()
    return user
