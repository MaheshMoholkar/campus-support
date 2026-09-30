from fastapi import APIRouter

from app.core.deps import CurrentUser, DbDep
from app.schemas.lookups import LookupsOut
from app.services import lookups as lookup_service

router = APIRouter(tags=["lookups"])


@router.get("/lookups", response_model=LookupsOut)
def get_lookups(db: DbDep, user: CurrentUser) -> LookupsOut:
    return lookup_service.lookups(db)
