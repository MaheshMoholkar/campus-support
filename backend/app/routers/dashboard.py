from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import DbDep, require_roles
from app.core.enums import Role
from app.models import User
from app.schemas.dashboard import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: DbDep, user: Annotated[User, Depends(require_roles(Role.LEAD, Role.ADMIN))]
) -> DashboardOut:
    return dashboard_service.dashboard(db)
