from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbDep, require_roles
from app.core.enums import Role
from app.models import ApprovalSection, ErpModule, Institute
from app.schemas.admin import (
    AdminUserOut,
    InstituteIn,
    InstituteOut,
    ModuleIn,
    ModuleOut,
    SectionIn,
    SectionOut,
    UserCreate,
    UserUpdate,
)
from app.services import admin

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(Role.ADMIN))]
)


@router.get("/institutes", response_model=list[InstituteOut])
def list_institutes(db: DbDep):
    return admin.list_rows(db, Institute)


@router.post("/institutes", response_model=InstituteOut, status_code=201)
def create_institute(data: InstituteIn, db: DbDep):
    row = admin.create_row(db, Institute, data.model_dump())
    db.commit()
    return row


@router.put("/institutes/{row_id}", response_model=InstituteOut)
def update_institute(row_id: int, data: InstituteIn, db: DbDep):
    row = admin.update_row(db, Institute, row_id, data.model_dump())
    db.commit()
    return row


@router.get("/sections", response_model=list[SectionOut])
def list_sections(db: DbDep):
    return admin.list_rows(db, ApprovalSection)


@router.post("/sections", response_model=SectionOut, status_code=201)
def create_section(data: SectionIn, db: DbDep):
    row = admin.create_row(db, ApprovalSection, data.model_dump())
    db.commit()
    return row


@router.put("/sections/{row_id}", response_model=SectionOut)
def update_section(row_id: int, data: SectionIn, db: DbDep):
    row = admin.update_row(db, ApprovalSection, row_id, data.model_dump())
    db.commit()
    return row


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(db: DbDep):
    return admin.list_rows(db, ErpModule)


@router.post("/modules", response_model=ModuleOut, status_code=201)
def create_module(data: ModuleIn, db: DbDep):
    row = admin.create_row(db, ErpModule, data.model_dump())
    db.commit()
    return row


@router.put("/modules/{row_id}", response_model=ModuleOut)
def update_module(row_id: int, data: ModuleIn, db: DbDep):
    row = admin.update_row(db, ErpModule, row_id, data.model_dump())
    db.commit()
    return row


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: DbDep):
    return admin.list_users(db)


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(data: UserCreate, db: DbDep):
    user = admin.create_user(db, data)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: UserUpdate, db: DbDep, actor: CurrentUser):
    user = admin.update_user(db, actor, user_id, data)
    db.commit()
    return user
