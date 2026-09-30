from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def str_enum(enum_cls: type[StrEnum]) -> SAEnum:
    """Map a StrEnum to a plain VARCHAR column that stores the enum's value."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=40,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
