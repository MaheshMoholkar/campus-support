from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models import ApprovalSection, ErpModule, Institute, User
from app.schemas.lookups import LookupsOut, ModuleOption, Option


def lookups(db: Session) -> LookupsOut:
    developers = db.scalars(
        select(User)
        .where(User.role == Role.DEVELOPER, User.is_active.is_(True))
        .order_by(User.name)
    )
    return LookupsOut(
        institutes=[
            Option.model_validate(row)
            for row in db.scalars(select(Institute).order_by(Institute.name))
        ],
        approval_sections=[
            Option.model_validate(row)
            for row in db.scalars(select(ApprovalSection).order_by(ApprovalSection.name))
        ],
        erp_modules=[
            ModuleOption.model_validate(row)
            for row in db.scalars(select(ErpModule).order_by(ErpModule.name))
        ],
        developers=[Option.model_validate(row) for row in developers],
    )
