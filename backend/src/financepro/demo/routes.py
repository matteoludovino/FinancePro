from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from financepro.demo.samples import sample

router = APIRouter(prefix="/samples", tags=["samples"])


@router.get("/{name}")
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
