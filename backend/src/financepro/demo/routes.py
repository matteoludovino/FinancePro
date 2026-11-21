from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from financepro.auth import sessions
from financepro.auth.schemas import UserOut
from financepro.db import get_db
from financepro.demo import sandbox
from financepro.demo.samples import sample

router = APIRouter(tags=["demo"])


@router.post("/demo/start", status_code=status.HTTP_201_CREATED)
def start_demo(db: Annotated[Session, Depends(get_db)], response: Response) -> UserOut:
    """A sandbox of one's own, signed in: no e-mail, no password, gone after 3 hours idle."""
    user = sandbox.create(db)
    sessions.start(db, response, user)
    return UserOut.model_validate(user)


@router.get("/samples/{name}")
def download_sample(name: str) -> Response:
    """Fictional statements to try the import with. Public: they hold no one's data."""
    content = sample(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Arquivo de exemplo não encontrado.")
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "max-age=3600"},
    )
