from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from financepro.auth.sessions import CurrentUser
from financepro.db import get_db
from financepro.importers import service
from financepro.importers.mapping import Mapping
from financepro.importers.reader import MAX_BYTES
from financepro.importers.schemas import BatchOut, ConfirmIn, UndoIn

router = APIRouter(prefix="/imports", tags=["imports"])

DB = Annotated[Session, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def upload(
    user: CurrentUser,
    db: DB,
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
) -> BatchOut:
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="O arquivo passa de 2 MB. Exporte um período menor.")
    batch = service.create_preview(db, user.id, account_id, file.filename or "", data)
    return BatchOut.of(batch)


@router.get("")
def list_imports(user: CurrentUser, db: DB) -> list[BatchOut]:
    return [BatchOut.of(batch, with_rows=False) for batch in service.list_batches(db, user.id)]


@router.get("/{batch_id}")
def get_import(batch_id: int, user: CurrentUser, db: DB) -> BatchOut:
    return BatchOut.of(service.get_batch(db, user.id, batch_id))


@router.put("/{batch_id}/mapping")
def remap(batch_id: int, body: Mapping, user: CurrentUser, db: DB) -> BatchOut:
    return BatchOut.of(service.remap(db, user.id, batch_id, body))


@router.post("/{batch_id}/confirm")
def confirm(batch_id: int, body: ConfirmIn, user: CurrentUser, db: DB) -> BatchOut:
    return BatchOut.of(service.confirm(db, user.id, batch_id, set(body.include_lines)))


@router.post("/{batch_id}/undo")
def undo(batch_id: int, body: UndoIn, user: CurrentUser, db: DB) -> BatchOut:
    return BatchOut.of(service.undo(db, user.id, batch_id, body.discard_edits), with_rows=False)


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel(batch_id: int, user: CurrentUser, db: DB) -> None:
    service.cancel(db, user.id, batch_id)
