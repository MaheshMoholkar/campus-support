from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.core.deps import CurrentUser, DbDep, StorageDep
from app.schemas.attachments import PresignIn, PresignOut
from app.services import attachments

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/presign", response_model=PresignOut)
def presign(data: PresignIn, storage: StorageDep, user: CurrentUser) -> PresignOut:
    key, upload_url = attachments.new_upload(
        storage, user, data.file_name, data.content_type, data.size_bytes
    )
    return PresignOut(key=key, upload_url=upload_url)


@router.get("/{attachment_id}/download")
def download(
    attachment_id: int, db: DbDep, storage: StorageDep, user: CurrentUser
) -> RedirectResponse:
    return RedirectResponse(
        attachments.download_url(db, storage, user, attachment_id), status_code=307
    )
