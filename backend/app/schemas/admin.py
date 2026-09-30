from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Role
from app.schemas.auth import UserOut

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Stripped(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class SectionIn(Stripped):
    name: str = Field(min_length=2, max_length=200)


class InstituteIn(SectionIn):
    code: str = Field(min_length=2, max_length=20)


class ModuleIn(SectionIn):
    url_prefix: str = Field(min_length=1, max_length=200)


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class InstituteOut(SectionOut):
    code: str


class ModuleOut(SectionOut):
    url_prefix: str


class UserCreate(Stripped):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    role: Role
    institute_id: int | None = None
    approval_section_id: int | None = None
    extension: str | None = Field(default=None, max_length=10)
    contact_number: str | None = Field(default=None, max_length=20)


class UserUpdate(Stripped):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    role: Role | None = None
    institute_id: int | None = None
    approval_section_id: int | None = None
    extension: str | None = Field(default=None, max_length=10)
    contact_number: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class AdminUserOut(UserOut):
    is_active: bool
    extension: str | None
    contact_number: str | None
