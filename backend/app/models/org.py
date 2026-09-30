from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.models.base import Base, str_enum, utcnow


class Institute(Base):
    __tablename__ = "institutes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)


class ApprovalSection(Base):
    __tablename__ = "approval_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)


class ErpModule(Base):
    __tablename__ = "erp_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    url_prefix: Mapped[str] = mapped_column(String(200))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(str_enum(Role))
    institute_id: Mapped[int | None] = mapped_column(ForeignKey("institutes.id"))
    approval_section_id: Mapped[int | None] = mapped_column(ForeignKey("approval_sections.id"))
    extension: Mapped[str | None] = mapped_column(String(10))
    contact_number: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
