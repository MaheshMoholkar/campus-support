from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Role


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: Role
    institute_id: int | None
    approval_section_id: int | None
